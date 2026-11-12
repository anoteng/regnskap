package eu.privatregnskap.app.ui.banksync

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.bank.BankSyncException
import eu.privatregnskap.app.data.bank.BankSyncRepository
import eu.privatregnskap.app.data.bank.Sb1Account
import eu.privatregnskap.app.data.bank.Sb1Link
import eu.privatregnskap.app.data.bank.Sb1Status
import eu.privatregnskap.app.data.bank.SyncOutcome
import eu.privatregnskap.app.data.bank.bankSyncMessage
import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.BankAccountResponse
import eu.privatregnskap.app.data.repository.LedgerSelectionRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import javax.inject.Inject

/** How far back the first fetch for a newly linked account goes. */
enum class SyncHistory(val label: String) {
    DAYS_30("30 dager"),
    DAYS_90("90 dager"),
    THIS_YEAR("I år"),
    ONE_YEAR("1 år"),
    FIVE_YEARS("5 år");

    fun startDate(today: LocalDate): LocalDate = when (this) {
        DAYS_30 -> today.minusDays(30)
        DAYS_90 -> today.minusDays(90)
        THIS_YEAR -> today.withDayOfYear(1)
        ONE_YEAR -> today.minusYears(1)
        // The bank gives five years at most
        FIVE_YEARS -> today.minusYears(5).plusDays(1)
    }
}

/** A link being put together: an account at the bank and where in the ledger it goes. */
data class LinkDraft(
    val ledgerId: Int,
    val ledgerName: String?,
    val accounts: List<Sb1Account>,
    val ledgerAccounts: List<BankAccountResponse>,
    val account: Sb1Account? = null,
    val ledgerAccountId: Int? = null,
    val history: SyncHistory = SyncHistory.DAYS_90
)

data class BankSyncUiState(
    val isLoading: Boolean = true,
    /** What is running right now, in words; null when nothing is. */
    val busy: String? = null,
    val message: String? = null,
    val error: String? = null,
    /** The bank's login page is open inside the app. */
    val loginUrl: String? = null,
    /** The bank's login page is open in the ordinary browser. */
    val browserLogin: Boolean = false,
    /** A new login was asked for while the old one still works. */
    val reLogin: Boolean = false,
    val linkDraft: LinkDraft? = null,
    /** What the server has to say about a connection, by connection id. */
    val serverErrors: Map<Int, String> = emptyMap(),
    /** Connections the server no longer has. */
    val missingConnections: Set<Int> = emptySet()
)

@HiltViewModel
class BankSyncViewModel @Inject constructor(
    private val bankSync: BankSyncRepository,
    private val apiService: ApiService,
    private val ledgerSelection: LedgerSelectionRepository
) : ViewModel() {

    val status: StateFlow<Sb1Status> = bankSync.status
    val isSyncing: StateFlow<Boolean> = bankSync.isSyncing

    private val _uiState = MutableStateFlow(BankSyncUiState())
    val uiState: StateFlow<BankSyncUiState> = _uiState.asStateFlow()

    private val _openInBrowser = MutableSharedFlow<String>(extraBufferCapacity = 1)

    /** Addresses the screen should hand to the device's browser. */
    val openInBrowser: SharedFlow<String> = _openInBrowser.asSharedFlow()

    init {
        viewModelScope.launch {
            try {
                bankSync.load()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.bankSyncMessage()) }
            }
            _uiState.update { it.copy(isLoading = false) }
            refreshServerStatus()
        }
        // A login that came back through the browser finishes outside this
        // view model. A new login time is how it shows.
        viewModelScope.launch {
            bankSync.status.map { it.loginAt }.distinctUntilChanged().collect { loginAt ->
                if (loginAt != null && _uiState.value.browserLogin) {
                    _uiState.update {
                        it.copy(browserLogin = false, reLogin = false, error = null, message = "Innlogget i banken")
                    }
                }
            }
        }
        viewModelScope.launch {
            bankSync.browserLoginFailures.collect { failure ->
                _uiState.update { it.copy(error = failure) }
            }
        }
    }

    /**
     * Runs one thing at a time and shows what it is. A login coming back from
     * the bank is not held up by this: its code is only good for two minutes.
     */
    private fun perform(busy: String, exclusive: Boolean = true, action: suspend () -> Unit) {
        if (exclusive && _uiState.value.busy != null) return
        _uiState.update { it.copy(busy = busy, error = null) }
        viewModelScope.launch {
            try {
                action()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _uiState.update { it.copy(error = e.bankSyncMessage()) }
            } finally {
                _uiState.update { it.copy(busy = null) }
            }
        }
    }

    fun consumeMessage() = _uiState.update { it.copy(message = null) }

    // ─── Keys ────────────────────────────────────────────────────────────────

    fun saveClient(clientId: String, clientSecret: String) {
        if (clientId.isBlank() || clientSecret.isBlank()) {
            _uiState.update { it.copy(error = "Fyll inn både Client ID og Client Secret.") }
            return
        }
        perform("Lagrer nøklene…") {
            bankSync.saveClient(clientId, clientSecret)
        }
    }

    fun removeKeys() = perform("Fjerner nøklene…") {
        bankSync.removeKeys()
        _uiState.update {
            BankSyncUiState(isLoading = false, busy = it.busy, message = "Nøklene er fjernet fra denne enheten")
        }
    }

    // ─── Login ───────────────────────────────────────────────────────────────

    fun startLogin() = perform("Åpner banken…") {
        val url = bankSync.beginLogin()
        bankSync.stopListening()
        _uiState.update { it.copy(loginUrl = url, browserLogin = false) }
    }

    fun cancelLogin() = _uiState.update { it.copy(loginUrl = null) }

    fun startBrowserLogin() = perform("Åpner banken…") {
        val url = bankSync.beginLogin()
        bankSync.listenForBrowserCallback()
        _uiState.update { it.copy(browserLogin = true) }
        _openInBrowser.emit(url)
    }

    fun browserMissing() {
        bankSync.stopListening()
        _uiState.update { it.copy(browserLogin = false, error = "Fant ingen nettleser på enheten.") }
    }

    fun askForNewLogin() = _uiState.update { it.copy(reLogin = true, error = null) }

    fun cancelNewLogin() {
        bankSync.stopListening()
        _uiState.update { it.copy(reLogin = false, browserLogin = false) }
    }

    /** The app's own browser view saw the bank send the user back. */
    fun onLoginCallback(address: String) {
        _uiState.update { it.copy(loginUrl = null) }
        finishLogin(address)
    }

    /** The user pasted the address the bank sent the browser to. */
    fun submitPastedAddress(address: String) {
        if (address.isBlank()) return
        finishLogin(address)
    }

    private fun finishLogin(address: String) = perform("Fullfører innloggingen…", exclusive = false) {
        bankSync.completeLogin(address)
        bankSync.stopListening()
        _uiState.update { it.copy(browserLogin = false, reLogin = false, message = "Innlogget i banken") }
        if (status.value.links.isNotEmpty()) sync()
    }

    // ─── Sync ────────────────────────────────────────────────────────────────

    fun syncNow() = perform("Henter fra banken…") { sync() }

    private suspend fun sync() {
        when (val outcome = bankSync.syncAll()) {
            is SyncOutcome.Done -> _uiState.update { it.copy(message = outcome.message) }
            is SyncOutcome.Failed -> _uiState.update { it.copy(error = outcome.message) }
            // The reason is kept with the stored status, which the screen shows
            SyncOutcome.NeedsLogin -> Unit
            SyncOutcome.Idle -> Unit
        }
        refreshServerStatus()
    }

    private suspend fun refreshServerStatus() {
        val links = status.value.links
        val errors = mutableMapOf<Int, String>()
        val missing = mutableSetOf<Int>()
        for (ledgerId in links.map { it.ledgerId }.distinct()) {
            val connections = try {
                bankSync.serverConnections(ledgerId)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                // Unknown is not the same as gone: say nothing about this ledger
                continue
            }
            for (link in links.filter { it.ledgerId == ledgerId }) {
                val connection = connections.firstOrNull { it.id == link.connectionId }
                if (connection == null) {
                    missing += link.connectionId
                } else {
                    connection.connectionError?.takeIf { it.isNotBlank() }?.let { errors[link.connectionId] = it }
                }
            }
        }
        _uiState.update { it.copy(serverErrors = errors, missingConnections = missing) }
    }

    // ─── Links ───────────────────────────────────────────────────────────────

    fun startLinking() = perform("Henter kontoer fra banken…") {
        ledgerSelection.ensureLoaded()
        val ledgerId = ledgerSelection.selected.value
            ?: throw BankSyncException("Velg et regnskap først.")
        val linked = status.value.links.filter { it.ledgerId == ledgerId }
        val accounts = bankSync.bankAccounts()
            .filter { account -> linked.none { it.accountNumber == account.accountNumber } }
        val ledgerAccounts = apiService.getBankAccounts(ledgerId)
            .filter { ledgerAccount -> linked.none { it.bankAccountId == ledgerAccount.id } }
        _uiState.update {
            it.copy(
                linkDraft = LinkDraft(
                    ledgerId = ledgerId,
                    ledgerName = ledgerSelection.selectedLedger?.name,
                    accounts = accounts,
                    ledgerAccounts = ledgerAccounts
                )
            )
        }
    }

    fun cancelLinking() = _uiState.update { it.copy(linkDraft = null) }

    fun selectAccount(account: Sb1Account) = _uiState.update { state ->
        val draft = state.linkDraft ?: return@update state
        // The same account number on both sides is very likely the same account
        val match = draft.ledgerAccounts.firstOrNull {
            val number = it.accountNumber?.filter(Char::isDigit)
            !number.isNullOrEmpty() && number == account.accountNumber.filter(Char::isDigit)
        }
        state.copy(linkDraft = draft.copy(account = account, ledgerAccountId = match?.id ?: draft.ledgerAccountId))
    }

    fun selectLedgerAccount(id: Int) = _uiState.update { state ->
        state.copy(linkDraft = state.linkDraft?.copy(ledgerAccountId = id))
    }

    fun selectHistory(history: SyncHistory) = _uiState.update { state ->
        state.copy(linkDraft = state.linkDraft?.copy(history = history))
    }

    fun confirmLink() {
        val draft = _uiState.value.linkDraft ?: return
        val account = draft.account ?: return
        val ledgerAccount = draft.ledgerAccounts.firstOrNull { it.id == draft.ledgerAccountId } ?: return
        perform("Kobler til og henter fra banken…") {
            bankSync.link(draft.ledgerId, ledgerAccount, account, draft.history.startDate(LocalDate.now()))
            _uiState.update { it.copy(linkDraft = null) }
            sync()
        }
    }

    fun unlink(link: Sb1Link) = perform("Kobler fra…") {
        bankSync.unlink(link)
        refreshServerStatus()
    }
}
