package eu.privatregnskap.app.ui.attachments

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.BuildConfig
import eu.privatregnskap.app.data.network.dto.AttachmentResponse
import eu.privatregnskap.app.data.network.dto.MatchSuggestionResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.repository.AttachmentRepository
import eu.privatregnskap.app.data.repository.LedgerRepository
import eu.privatregnskap.app.data.repository.TokenRepository
import eu.privatregnskap.app.data.repository.TransactionRepository
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AttachmentsUiState(
    val attachments: List<AttachmentResponse> = emptyList(),
    val isLoading: Boolean = false,
    val isUploading: Boolean = false,
    val extractingId: Int? = null,
    val error: String? = null,
    val requiresSubscription: Boolean = false
)

@HiltViewModel
class AttachmentsViewModel @Inject constructor(
    private val repository: AttachmentRepository,
    private val transactionRepository: TransactionRepository,
    private val ledgerRepository: LedgerRepository,
    private val tokenRepository: TokenRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AttachmentsUiState())
    val uiState: StateFlow<AttachmentsUiState> = _uiState.asStateFlow()

    private val _transactions = MutableStateFlow<List<TransactionResponse>>(emptyList())
    val transactions: StateFlow<List<TransactionResponse>> = _transactions.asStateFlow()

    private val _suggestedMatches = MutableStateFlow<List<MatchSuggestionResponse>>(emptyList())
    val suggestedMatches: StateFlow<List<MatchSuggestionResponse>> = _suggestedMatches.asStateFlow()

    private val _message = MutableSharedFlow<String>()
    val message = _message.asSharedFlow()

    private var currentLedgerId: Int? = null
    private var currentStatusFilter: String? = null
    private var currentSearch: String? = null

    init {
        loadAll()
    }

    fun imageUrl(id: Int): String {
        val token = tokenRepository.getAccessToken() ?: ""
        val ledger = currentLedgerId ?: ""
        return "${BuildConfig.BASE_URL}receipts/$id/image?token=$token&ledger=$ledger"
    }

    fun loadAll(statusFilter: String? = currentStatusFilter, search: String? = currentSearch) {
        currentStatusFilter = statusFilter
        currentSearch = search
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            if (currentLedgerId == null) {
                ledgerRepository.getLedgers().onSuccess { list ->
                    currentLedgerId = list.firstOrNull()?.id
                }.onFailure {
                    _uiState.value = AttachmentsUiState(error = "Kunne ikke laste regnskaper")
                    return@launch
                }
            }

            repository.getAttachments(currentLedgerId, statusFilter, search?.ifBlank { null }).fold(
                onSuccess = { list ->
                    _uiState.value = AttachmentsUiState(attachments = list)
                },
                onFailure = { e ->
                    if (e.message?.contains("403") == true) {
                        _uiState.value = AttachmentsUiState(requiresSubscription = true)
                    } else {
                        _uiState.value = AttachmentsUiState(error = e.message ?: "Ukjent feil")
                    }
                }
            )
        }
    }

    fun loadTransactionsForMatching() {
        viewModelScope.launch {
            transactionRepository.getTransactions(currentLedgerId, limit = 100).onSuccess {
                _transactions.value = it
            }
        }
    }

    fun loadSuggestedMatches(receiptId: Int) {
        viewModelScope.launch {
            _suggestedMatches.value = emptyList()
            repository.suggestMatches(currentLedgerId, receiptId).onSuccess {
                _suggestedMatches.value = it
            }
        }
    }

    fun upload(
        context: Context,
        uri: Uri,
        attachmentType: String,
        receiptDate: String?,
        dueDate: String?,
        amount: String?,
        description: String?
    ) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isUploading = true)
            try {
                val contentResolver = context.contentResolver
                val mimeType = contentResolver.getType(uri) ?: "image/jpeg"
                val fileName = uri.lastPathSegment?.let {
                    if (it.contains('.')) it else "$it.jpg"
                } ?: "attachment.jpg"
                val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() }
                    ?: throw Exception("Kunne ikke lese fil")

                repository.uploadAttachment(
                    currentLedgerId, bytes, fileName, mimeType,
                    attachmentType, receiptDate, dueDate, amount, description
                ).fold(
                    onSuccess = {
                        _message.emit("Vedlegg lastet opp")
                        loadAll()
                    },
                    onFailure = { e ->
                        _uiState.value = _uiState.value.copy(isUploading = false)
                        _message.emit(
                            if (e.message?.contains("403") == true)
                                "Vedlegg krever Basic- eller Premium-abonnement"
                            else "Opplasting feilet: ${e.message}"
                        )
                    }
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isUploading = false)
                _message.emit("Feil: ${e.message}")
            }
        }
    }

    fun delete(id: Int) {
        viewModelScope.launch {
            repository.deleteAttachment(currentLedgerId, id).fold(
                onSuccess = { _message.emit("Vedlegg slettet"); loadAll() },
                onFailure = { _message.emit("Kunne ikke slette: ${it.message}") }
            )
        }
    }

    fun extractAI(id: Int) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(extractingId = id)
            repository.extractAI(currentLedgerId, id).fold(
                onSuccess = { updated ->
                    val list = _uiState.value.attachments.map { if (it.id == id) updated else it }
                    _uiState.value = _uiState.value.copy(attachments = list, extractingId = null)
                    _message.emit("AI-gjenkjenning fullført")
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(extractingId = null)
                    _message.emit(
                        if (e.message?.contains("403") == true)
                            "AI-gjenkjenning krever Premium-abonnement"
                        else "AI-gjenkjenning feilet: ${e.message}"
                    )
                }
            )
        }
    }

    fun matchAttachment(attachmentId: Int, transactionId: Int) {
        viewModelScope.launch {
            repository.matchAttachment(currentLedgerId, attachmentId, transactionId).fold(
                onSuccess = { _message.emit("Vedlegg koblet til transaksjon"); loadAll() },
                onFailure = { _message.emit("Kunne ikke koble: ${it.message}") }
            )
        }
    }

    fun unmatchAttachment(id: Int) {
        viewModelScope.launch {
            repository.unmatchAttachment(currentLedgerId, id).fold(
                onSuccess = { _message.emit("Kobling fjernet"); loadAll() },
                onFailure = { _message.emit("Kunne ikke fjerne kobling: ${it.message}") }
            )
        }
    }
}
