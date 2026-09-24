package eu.privatregnskap.app.ui.settlement

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.AccountResponse
import eu.privatregnskap.app.data.network.dto.SettlementMemberInput
import eu.privatregnskap.app.data.network.dto.SettlementSettingsRequest
import eu.privatregnskap.app.data.repository.LedgerRepository
import eu.privatregnskap.app.data.repository.PostingQueueRepository
import eu.privatregnskap.app.data.repository.SettlementRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.json.JSONObject
import retrofit2.HttpException
import javax.inject.Inject

data class SettlementMemberRow(
    val userId: Int,
    val name: String,
    val email: String,
    val sharePercent: String,
    val depositAccountId: Int?
)

data class SettlementSetupUiState(
    val isLoading: Boolean = true,
    val isSaving: Boolean = false,
    val loadError: String? = null,
    val saveError: String? = null,
    val saved: Boolean = false,
    /** Only the ledger owner may change these settings (PUT is owner-only). */
    val canEdit: Boolean = false,
    val isEnabled: Boolean = false,
    val operatingAccountId: Int? = null,
    val lookbackMonths: Int = 3,
    val members: List<SettlementMemberRow> = emptyList(),
    val excludedAccountIds: Set<Int> = emptySet(),
    val accounts: List<AccountResponse> = emptyList()
) {
    val assetAccounts: List<AccountResponse>
        get() = accounts.filter { it.accountType == "ASSET" }

    val expenseAccounts: List<AccountResponse>
        get() = accounts.filter { it.accountType == "EXPENSE" }

    /** Deposits are booked on revenue/equity accounts, never on expense accounts. */
    val depositCandidates: List<AccountResponse>
        get() = accounts.filter { it.accountType != "EXPENSE" }

    val shareSum: Double
        get() = members.sumOf { it.sharePercent.replace(',', '.').toDoubleOrNull() ?: 0.0 }
}

@HiltViewModel
class SettlementSetupViewModel @Inject constructor(
    private val settlementRepository: SettlementRepository,
    private val ledgerRepository: LedgerRepository,
    private val postingQueueRepository: PostingQueueRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettlementSetupUiState())
    val uiState: StateFlow<SettlementSetupUiState> = _uiState.asStateFlow()

    private var ledgerId: Int? = null

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, loadError = null, saved = false) }

            val ledger = ledgerRepository.getLedgers().getOrNull()?.firstOrNull()
            if (ledger == null) {
                _uiState.update { it.copy(isLoading = false, loadError = "Fant ingen regnskap") }
                return@launch
            }
            ledgerId = ledger.id

            val settings = settlementRepository.getSettings(ledger.id).getOrElse { e ->
                _uiState.update {
                    it.copy(isLoading = false, loadError = e.message ?: "Kunne ikke hente innstillinger")
                }
                return@launch
            }
            val ledgerMembers = ledgerRepository.getMembers(ledger.id).getOrElse { e ->
                _uiState.update {
                    it.copy(isLoading = false, loadError = e.message ?: "Kunne ikke hente medlemmer")
                }
                return@launch
            }
            val accounts = postingQueueRepository.getAccounts(ledger.id).getOrDefault(emptyList())

            val configured = settings.members.associateBy { it.userId }
            val rows = ledgerMembers.map { m ->
                val cfg = configured[m.userId]
                SettlementMemberRow(
                    userId = m.userId,
                    name = m.user.fullName,
                    email = m.user.email,
                    sharePercent = cfg?.sharePercent?.trimZeros()
                        ?: if (ledgerMembers.size == 1) "100" else "",
                    depositAccountId = cfg?.depositAccountId
                )
            }

            _uiState.update {
                it.copy(
                    isLoading = false,
                    canEdit = ledger.userRole == "OWNER",
                    isEnabled = settings.isEnabled,
                    operatingAccountId = settings.operatingAccountId,
                    lookbackMonths = settings.variableLookbackMonths,
                    members = rows,
                    excludedAccountIds = settings.excludedAccountIds.toSet(),
                    accounts = accounts
                )
            }
        }
    }

    fun setEnabled(enabled: Boolean) = _uiState.update { it.copy(isEnabled = enabled, saveError = null) }

    fun setOperatingAccount(accountId: Int?) = _uiState.update { it.copy(operatingAccountId = accountId) }

    fun setLookbackMonths(months: Int) =
        _uiState.update { it.copy(lookbackMonths = months.coerceIn(1, 24)) }

    fun setShare(userId: Int, value: String) = _uiState.update { state ->
        state.copy(members = state.members.map {
            if (it.userId == userId) it.copy(sharePercent = value) else it
        })
    }

    fun setDepositAccount(userId: Int, accountId: Int?) = _uiState.update { state ->
        state.copy(members = state.members.map {
            if (it.userId == userId) it.copy(depositAccountId = accountId) else it
        })
    }

    fun distributeEvenly() = _uiState.update { state ->
        if (state.members.isEmpty()) return@update state
        // Split in hundredths of a percent so the shares always total exactly 100
        val base = 10000 / state.members.size
        val remainder = 10000 % state.members.size
        state.copy(members = state.members.mapIndexed { index, m ->
            val hundredths = base + if (index < remainder) 1 else 0
            m.copy(sharePercent = (hundredths / 100.0).trimZeros())
        })
    }

    fun toggleExcluded(accountId: Int) = _uiState.update { state ->
        val next = state.excludedAccountIds.toMutableSet()
        if (!next.add(accountId)) next.remove(accountId)
        state.copy(excludedAccountIds = next)
    }

    fun save() {
        val state = _uiState.value
        val id = ledgerId ?: return

        viewModelScope.launch {
            _uiState.update { it.copy(isSaving = true, saveError = null) }

            val request = SettlementSettingsRequest(
                isEnabled = state.isEnabled,
                operatingAccountId = state.operatingAccountId,
                variableLookbackMonths = state.lookbackMonths,
                members = state.members.mapNotNull { m ->
                    val share = m.sharePercent.replace(',', '.').toDoubleOrNull()
                    if (share == null || share <= 0.0) null
                    else SettlementMemberInput(m.userId, share, m.depositAccountId)
                },
                excludedAccountIds = state.excludedAccountIds.toList().sorted()
            )

            settlementRepository.updateSettings(id, request).fold(
                onSuccess = { _uiState.update { s -> s.copy(isSaving = false, saved = true) } },
                // The backend validates the same rules and answers in Norwegian
                onFailure = { e ->
                    _uiState.update { s ->
                        s.copy(isSaving = false, saveError = e.toUserMessage())
                    }
                }
            )
        }
    }

    fun consumeSaved() = _uiState.update { it.copy(saved = false) }
}

private fun String.trimZeros(): String {
    val value = replace(',', '.').toDoubleOrNull() ?: return this
    return value.trimZeros()
}

private fun Double.trimZeros(): String =
    if (this == toLong().toDouble()) toLong().toString() else toString()

/** Backend validation errors arrive as {"detail": "..."} and are already in Norwegian. */
private fun Throwable.toUserMessage(): String {
    if (this is HttpException) {
        val detail = runCatching {
            response()?.errorBody()?.string()?.let { JSONObject(it).optString("detail") }
        }.getOrNull()
        if (!detail.isNullOrBlank()) return detail
    }
    return message ?: "Kunne ikke lagre innstillingene"
}
