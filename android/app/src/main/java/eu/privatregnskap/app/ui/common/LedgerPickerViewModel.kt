package eu.privatregnskap.app.ui.common

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.LedgerResponse
import eu.privatregnskap.app.data.repository.LedgerSelectionRepository
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class LedgerPickerViewModel @Inject constructor(
    private val ledgerSelection: LedgerSelectionRepository
) : ViewModel() {

    val ledgers: StateFlow<List<LedgerResponse>> = ledgerSelection.ledgers
    val selectedLedgerId: StateFlow<Int?> = ledgerSelection.selected

    init {
        // Pick up ledgers created or shared since the app was opened
        viewModelScope.launch { ledgerSelection.ensureLoaded(forceRefresh = true) }
    }

    fun select(ledgerId: Int) {
        viewModelScope.launch { ledgerSelection.select(ledgerId) }
    }
}
