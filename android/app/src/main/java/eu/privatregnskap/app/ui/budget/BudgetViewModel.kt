package eu.privatregnskap.app.ui.budget

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.BudgetReportResponse
import eu.privatregnskap.app.data.network.dto.BudgetResponse
import eu.privatregnskap.app.data.repository.BudgetRepository
import eu.privatregnskap.app.data.repository.LedgerRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class BudgetUiState(
    val budgets: List<BudgetResponse> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null
)

data class BudgetReportUiState(
    val report: BudgetReportResponse? = null,
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class BudgetViewModel @Inject constructor(
    private val budgetRepository: BudgetRepository,
    private val ledgerRepository: LedgerRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(BudgetUiState())
    val uiState: StateFlow<BudgetUiState> = _uiState.asStateFlow()

    private val _reportState = MutableStateFlow(BudgetReportUiState())
    val reportState: StateFlow<BudgetReportUiState> = _reportState.asStateFlow()

    private var currentLedgerId: Int? = null

    init {
        loadBudgets()
    }

    fun loadBudgets() {
        viewModelScope.launch {
            _uiState.value = BudgetUiState(isLoading = true)
            if (currentLedgerId == null) {
                ledgerRepository.getLedgers().onSuccess { list ->
                    currentLedgerId = list.firstOrNull()?.id
                }.onFailure {
                    _uiState.value = BudgetUiState(error = "Kunne ikke laste regnskaper")
                    return@launch
                }
            }
            budgetRepository.getBudgets(currentLedgerId).fold(
                onSuccess = { _uiState.value = BudgetUiState(budgets = it) },
                onFailure = { _uiState.value = BudgetUiState(error = it.message ?: "Ukjent feil") }
            )
        }
    }

    fun loadReport(budgetId: Int) {
        viewModelScope.launch {
            _reportState.value = BudgetReportUiState(isLoading = true)
            budgetRepository.getBudgetReport(currentLedgerId, budgetId).fold(
                onSuccess = { _reportState.value = BudgetReportUiState(report = it) },
                onFailure = { _reportState.value = BudgetReportUiState(error = it.message ?: "Ukjent feil") }
            )
        }
    }

    fun clearReport() {
        _reportState.value = BudgetReportUiState()
    }
}
