package eu.privatregnskap.app.ui.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.SettlementCalculationResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.repository.LedgerRepository
import eu.privatregnskap.app.data.repository.SettlementRepository
import eu.privatregnskap.app.data.repository.TransactionRepository
import eu.privatregnskap.app.ui.auth.UiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class DashboardViewModel @Inject constructor(
    private val transactionRepository: TransactionRepository,
    private val ledgerRepository: LedgerRepository,
    private val settlementRepository: SettlementRepository
) : ViewModel() {

    private val _transactionsState = MutableStateFlow<UiState<List<TransactionResponse>>>(UiState.Idle)
    val transactionsState: StateFlow<UiState<List<TransactionResponse>>> = _transactionsState.asStateFlow()

    // Success(null) = settlement not enabled for this ledger, so the card stays
    // hidden; Error means the load failed and the user should be told
    private val _settlementState = MutableStateFlow<UiState<SettlementCalculationResponse?>>(UiState.Idle)
    val settlementState: StateFlow<UiState<SettlementCalculationResponse?>> = _settlementState.asStateFlow()

    private var currentLedgerId: Int? = null

    init {
        loadTransactions()
    }

    fun loadTransactions() {
        viewModelScope.launch {
            _transactionsState.value = UiState.Loading
            if (currentLedgerId == null) {
                val ledgers = ledgerRepository.getLedgers()
                ledgers.onSuccess { list ->
                    currentLedgerId = list.firstOrNull()?.id
                }
                if (ledgers.isFailure) {
                    _transactionsState.value = UiState.Error(
                        ledgers.exceptionOrNull()?.message ?: "Kunne ikke laste regnskaper"
                    )
                    return@launch
                }
            }
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
