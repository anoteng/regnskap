package eu.privatregnskap.app.ui.main

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.repository.LedgerSelectionRepository
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class MainViewModel @Inject constructor(
    private val ledgerSelection: LedgerSelectionRepository
) : ViewModel() {

    /** When true the user has no ledgers at all and must create one first. */
    val hasNoLedgers: StateFlow<Boolean> = ledgerSelection.hasNoLedgers

    init {
        viewModelScope.launch { ledgerSelection.ensureLoaded() }
    }
}
