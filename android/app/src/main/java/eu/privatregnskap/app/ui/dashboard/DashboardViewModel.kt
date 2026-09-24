package eu.privatregnskap.app.ui.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.SettlementCalculationResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.repository.LedgerSelectionRepository
import eu.privatregnskap.app.data.repository.SettlementRepository
import eu.privatregnskap.app.data.repository.TransactionRepository
import eu.privatregnskap.app.ui.auth.UiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val transactionRepository: TransactionRepository,
    private val ledgerSelection: LedgerSelectionRepository,
    private val settlementRepository: SettlementRepository
) : ViewModel() {

    private val _transactionsState = MutableStateFlow<UiState<List<TransactionResponse>>>(UiState.Idle)
    val transactionsState: StateFlow<UiState<List<TransactionResponse>>> = _transactionsState.asStateFlow()

    // Success(null) = settlement not enabled for this ledger, so the card stays
    // hidden; Error means the load failed and the user should be told
    private val _settlementState = MutableStateFlow<UiState<SettlementCalculationResponse?>>(UiState.Idle)
    val settlementState: StateFlow<UiState<SettlementCalculationResponse?>> = _settlementState.asStateFlow()

    val ledgerName: StateFlow<String?> =
        combine(ledgerSelection.ledgers, ledgerSelection.selected) { list, id ->
            list.firstOrNull { it.id == id }?.name
        }.stateIn(viewModelScope, SharingStarted.Eagerly, null)

    private var currentLedgerId: Int? = null

    init {
        viewModelScope.launch {
            ledgerSelection.ensureLoaded().onFailure {
                _transactionsState.value = UiState.Error(it.message ?: "Kunne ikke laste regnskaper")
            }
            // Reloads every time the user switches ledger
            ledgerSelection.selectedLedgerId.collect { id ->
                currentLedgerId = id
                loadTransactions()
            }
        }
    }

    fun loadTransactions() {
        viewModelScope.launch {
            _transactionsState.value = UiState.Loading
            val result = transactionRepository.getTransactions(ledgerId = currentLedgerId, limit = 50)
            _transactionsState.value = result.fold(
                onSuccess = { UiState.Success(it) },
                onFailure = { UiState.Error(it.message ?: "Kunne ikke laste transaksjoner") }
            )
            loadSettlement()
        }
    }

    private fun loadSettlement() {
        viewModelScope.launch {
            _settlementState.value = settlementRepository
                .getCalculation(currentLedgerId, month = null)
                .fold(
                    onSuccess = { UiState.Success(it) },
                    onFailure = { UiState.Error(it.message ?: "Ukjent feil") }
                )
        }
    }
}
