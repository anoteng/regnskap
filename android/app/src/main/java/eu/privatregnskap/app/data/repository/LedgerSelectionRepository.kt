package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.ChartTemplateResponse
import eu.privatregnskap.app.data.network.dto.CreateLedgerRequest
import eu.privatregnskap.app.data.network.dto.LedgerResponse
import eu.privatregnskap.app.data.preferences.LedgerPreferences
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

/**
 * The one place that decides which ledger the app is working in.
 *
 * Screens observe [selectedLedgerId] and reload when it changes, so switching
 * ledger updates every tab. The stored choice is only honoured while it is
 * still one of the user's ledgers — otherwise a ledger left behind by a
 * previous user (or one access was revoked to) would make every request fail.
 */
@Singleton
class LedgerSelectionRepository @Inject constructor(
    private val apiService: ApiService,
    private val preferences: LedgerPreferences
) {
    private val _ledgers = MutableStateFlow<List<LedgerResponse>>(emptyList())
    val ledgers: StateFlow<List<LedgerResponse>> = _ledgers.asStateFlow()

    private val _selectedLedgerId = MutableStateFlow<Int?>(null)

    /** Emits only once a valid ledger is known, so screens never load with a null id. */
    val selectedLedgerId: Flow<Int> = _selectedLedgerId.filterNotNull().distinctUntilChanged()

    val selected: StateFlow<Int?> = _selectedLedgerId.asStateFlow()

    val selectedLedger: LedgerResponse?
        get() = _ledgers.value.firstOrNull { it.id == _selectedLedgerId.value }

    /** Loads the ledger list and resolves which one is active. Safe to call repeatedly. */
    suspend fun ensureLoaded(forceRefresh: Boolean = false): Result<List<LedgerResponse>> {
        if (!forceRefresh && _ledgers.value.isNotEmpty() && _selectedLedgerId.value != null) {
            return Result.success(_ledgers.value)
        }
        return runCatching { apiService.getLedgers() }.onSuccess { list ->
            _ledgers.value = list
            val stored = preferences.selectedLedgerId.first()
            val resolved = list.firstOrNull { it.id == stored } ?: list.firstOrNull()
            _selectedLedgerId.value = resolved?.id
            _hasNoLedgers.value = list.isEmpty()
        }
    }

    suspend fun select(ledgerId: Int) {
        // Always persist, even when the id is unchanged: a freshly created
        // ledger may already be the resolved one, and the choice must stick
        preferences.setSelectedLedgerId(ledgerId)
        _selectedLedgerId.value = ledgerId
        // Keep the web session pointing at the same ledger
        runCatching { apiService.switchLedger(ledgerId) }
    }

    /** True once the ledger list is known to be empty — the app has nothing to show. */
    private val _hasNoLedgers = MutableStateFlow(false)
    val hasNoLedgers: StateFlow<Boolean> = _hasNoLedgers.asStateFlow()

    suspend fun chartTemplates(): Result<List<ChartTemplateResponse>> =
        runCatching { apiService.getChartTemplates() }

    /** Creates a ledger and makes it the active one. */
    suspend fun createLedger(request: CreateLedgerRequest): Result<LedgerResponse> =
        runCatching { apiService.createLedger(request) }.onSuccess { created ->
            ensureLoaded(forceRefresh = true)
            select(created.id)
        }

    suspend fun clear() {
        preferences.clear()
        _selectedLedgerId.value = null
        _ledgers.value = emptyList()
        _hasNoLedgers.value = false
    }
}
