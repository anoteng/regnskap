package eu.privatregnskap.app.ui.transactions

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.AttachmentResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.repository.AttachmentRepository
import eu.privatregnskap.app.data.repository.LedgerSelectionRepository
import eu.privatregnskap.app.data.repository.TransactionRepository
import eu.privatregnskap.app.ui.auth.UiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class TransactionDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val transactionRepository: TransactionRepository,
    private val attachmentRepository: AttachmentRepository,
    private val ledgerSelection: LedgerSelectionRepository
) : ViewModel() {

    private val transactionId: Int = savedStateHandle.get<String>("id")?.toIntOrNull() ?: 0

    private val _transaction = MutableStateFlow<UiState<TransactionResponse>>(UiState.Loading)
    val transaction: StateFlow<UiState<TransactionResponse>> = _transaction.asStateFlow()

    // Attachments are extra information, so a failure here leaves the voucher
    // itself readable rather than blanking the screen
    private val _attachments = MutableStateFlow<List<AttachmentResponse>>(emptyList())
    val attachments: StateFlow<List<AttachmentResponse>> = _attachments.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            val ledgerId = ledgerSelection.selectedLedgerId.first()
            _transaction.value = UiState.Loading
            _transaction.value = transactionRepository
                .getTransaction(id = transactionId, ledgerId = ledgerId)
                .fold(
                    onSuccess = { UiState.Success(it) },
                    onFailure = { UiState.Error(it.message ?: "Kunne ikke hente transaksjonen") }
                )
            attachmentRepository
                .getAttachments(ledgerId = ledgerId, transactionId = transactionId)
                .onSuccess { _attachments.value = it }
        }
    }
}
