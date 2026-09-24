package eu.privatregnskap.app.ui.ledger

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.BankAccountSetupRequest
import eu.privatregnskap.app.data.network.dto.ChartTemplateResponse
import eu.privatregnskap.app.data.network.dto.CreateLedgerRequest
import eu.privatregnskap.app.data.repository.LedgerSelectionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/** A bank account being filled in before the ledger exists. */
data class NewBankAccount(
    val id: Long,
    val name: String = "",
    val accountType: String = "CHECKING"
)

data class CreateLedgerUiState(
    val isLoading: Boolean = true,
    val isSaving: Boolean = false,
    val error: String? = null,
    val templates: List<ChartTemplateResponse> = emptyList(),
    val selectedTemplateId: Int? = null,
    val name: String = "",
    /** True once the user edits the name, so template changes stop overwriting it. */
    val nameEdited: Boolean = false,
    val bankAccounts: List<NewBankAccount> = emptyList(),
    val createdLedgerId: Int? = null
) {
    val canSubmit: Boolean
        get() = !isSaving && name.isNotBlank() && selectedTemplateId != null
}

/** Suggested ledger names per template, matching the web onboarding. */
private val DEFAULT_NAMES = mapOf(
    "personal_accounting" to "Mitt regnskap",
    "family_accounting" to "Familieregnskap",
    "business_accounting" to "Mitt firma"
)

val BANK_ACCOUNT_TYPES = listOf(
    "CHECKING" to "Brukskonto",
    "SAVINGS" to "Sparekonto",
    "CREDIT_CARD" to "Kredittkort"
)

@HiltViewModel
class CreateLedgerViewModel @Inject constructor(
    private val ledgerSelection: LedgerSelectionRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(CreateLedgerUiState())
    val uiState: StateFlow<CreateLedgerUiState> = _uiState.asStateFlow()

    private var nextBankAccountId = 1L

    init {
        loadTemplates()
    }

    fun loadTemplates() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            ledgerSelection.chartTemplates().fold(
                onSuccess = { templates ->
                    val first = templates.firstOrNull()
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            templates = templates,
                            selectedTemplateId = it.selectedTemplateId ?: first?.id,
                            name = if (it.nameEdited) it.name else suggestedName(first)
                        )
                    }
                },
                onFailure = { e ->
                    _uiState.update {
                        it.copy(isLoading = false, error = e.message ?: "Kunne ikke hente kontoplaner")
                    }
                }
            )
        }
    }

    fun selectTemplate(templateId: Int) = _uiState.update { state ->
        val template = state.templates.firstOrNull { it.id == templateId }
        state.copy(
            selectedTemplateId = templateId,
            name = if (state.nameEdited) state.name else suggestedName(template)
        )
    }

    fun setName(name: String) = _uiState.update { it.copy(name = name, nameEdited = true) }

    fun addBankAccount() = _uiState.update { state ->
        state.copy(bankAccounts = state.bankAccounts + NewBankAccount(id = nextBankAccountId++))
    }

    fun setBankAccountName(id: Long, name: String) = _uiState.update { state ->
        state.copy(bankAccounts = state.bankAccounts.map {
            if (it.id == id) it.copy(name = name) else it
        })
    }

    fun setBankAccountType(id: Long, type: String) = _uiState.update { state ->
        state.copy(bankAccounts = state.bankAccounts.map {
            if (it.id == id) it.copy(accountType = type) else it
        })
    }

    fun removeBankAccount(id: Long) = _uiState.update { state ->
        state.copy(bankAccounts = state.bankAccounts.filterNot { it.id == id })
    }

    fun create() {
        val state = _uiState.value
        if (!state.canSubmit) return

        viewModelScope.launch {
            _uiState.update { it.copy(isSaving = true, error = null) }

            val accounts = state.bankAccounts
                .filter { it.name.isNotBlank() }
                .map { BankAccountSetupRequest(name = it.name.trim(), accountType = it.accountType) }

            val request = CreateLedgerRequest(
                name = state.name.trim(),
                chartTemplateId = state.selectedTemplateId,
                bankAccounts = accounts.ifEmpty { null }
            )

            ledgerSelection.createLedger(request).fold(
                onSuccess = { ledger ->
                    _uiState.update { it.copy(isSaving = false, createdLedgerId = ledger.id) }
                },
                onFailure = { e ->
                    _uiState.update {
                        it.copy(isSaving = false, error = e.message ?: "Kunne ikke opprette regnskapet")
                    }
                }
            )
        }
    }

    private fun suggestedName(template: ChartTemplateResponse?): String =
        template?.let { DEFAULT_NAMES[it.name] ?: it.displayName } ?: ""
}
