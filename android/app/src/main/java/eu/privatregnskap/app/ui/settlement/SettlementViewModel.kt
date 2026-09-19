package eu.privatregnskap.app.ui.settlement

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.SettlementCalculationResponse
import eu.privatregnskap.app.data.repository.LedgerRepository
import eu.privatregnskap.app.data.repository.SettlementRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.YearMonth
import javax.inject.Inject

data class SettlementUiState(
    val month: YearMonth = YearMonth.now(),
    val calculation: SettlementCalculationResponse? = null,
    val isEnabled: Boolean = true,
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class SettlementViewModel @Inject constructor(
    private val settlementRepository: SettlementRepository,
    private val ledgerRepository: LedgerRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettlementUiState())
    val uiState: StateFlow<SettlementUiState> = _uiState.asStateFlow()

    private var currentLedgerId: Int? = null

    init {
        load()
    }

    fun previousMonth() = setMonth(_uiState.value.month.minusMonths(1))
    fun nextMonth() = setMonth(_uiState.value.month.plusMonths(1))
    fun currentMonth() = setMonth(YearMonth.now())

    private fun setMonth(month: YearMonth) {
        _uiState.value = _uiState.value.copy(month = month)
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            if (currentLedgerId == null) {
                ledgerRepository.getLedgers().fold(
                    onSuccess = { currentLedgerId = it.firstOrNull()?.id },
                    onFailure = {
                        _uiState.value = _uiState.value.copy(isLoading = false, error = "Kunne ikke laste regnskaper")
                        return@launch
                    }
                )
            }
            val month = _uiState.value.month.toString()
            settlementRepository.getCalculation(currentLedgerId, month).fold(
                onSuccess = { calc ->
                    _uiState.value = _uiState.value.copy(
                        calculation = calc,
                        isEnabled = calc != null,
                        isLoading = false
                    )
                },
                onFailure = {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = it.message ?: "Kunne ikke hente avregning"
                    )
                }
            )
        }
    }
}
