package eu.privatregnskap.app.ui.transactions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.repository.LedgerSelectionRepository
import eu.privatregnskap.app.data.repository.TransactionRepository
import eu.privatregnskap.app.ui.auth.UiState
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/** How many hits the server returns before the list is truncated. */
const val SEARCH_LIMIT = 100

@HiltViewModel
class TransactionSearchViewModel @Inject constructor(
    private val transactionRepository: TransactionRepository,
    private val ledgerSelection: LedgerSelectionRepository
) : ViewModel() {

    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()

    // Idle means nothing has been typed yet, which the screen shows as a hint
    // rather than as an empty result
    private val _results = MutableStateFlow<UiState<List<TransactionResponse>>>(UiState.Idle)
    val results: StateFlow<UiState<List<TransactionResponse>>> = _results.asStateFlow()

    private var currentLedgerId: Int? = null
    private var searchJob: Job? = null

    init {
        viewModelScope.launch {
            ledgerSelection.selectedLedgerId.collect { id ->
                currentLedgerId = id
                // Switching ledger mid-search would otherwise leave the old
                // ledger's hits on screen under the new ledger's name
                if (_query.value.isNotBlank()) search(_query.value)
            }
        }
    }

    fun onQueryChange(text: String) {
        _query.value = text
        searchJob?.cancel()
        if (text.isBlank()) {
            _results.value = UiState.Idle
            return
        }
        // The search spans journal lines and account names, so it is heavier
        // than the attachment search. Wait for a pause in typing rather than
        // firing a query per keystroke.
        searchJob = viewModelScope.launch {
            delay(300)
            search(text)
        }
    }

    fun clear() {
        searchJob?.cancel()
        _query.value = ""
        _results.value = UiState.Idle
    }

    private suspend fun search(text: String) {
        _results.value = UiState.Loading
        _results.value = transactionRepository
            .getTransactions(ledgerId = currentLedgerId, limit = SEARCH_LIMIT, search = text)
            .fold(
                onSuccess = { UiState.Success(it) },
                onFailure = { UiState.Error(it.message ?: "Søket feilet") }
            )
    }
}
