package eu.privatregnskap.app.ui.attachments

import android.content.Context
import android.net.Uri
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.BuildConfig
import eu.privatregnskap.app.data.network.dto.AccountResponse
import eu.privatregnskap.app.data.network.dto.AttachmentResponse
import eu.privatregnskap.app.data.network.dto.MatchSuggestionResponse
import eu.privatregnskap.app.data.network.dto.PlannedTransactionResponse
import eu.privatregnskap.app.data.network.dto.ReceiptUpdateRequest
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.repository.AttachmentRepository
import eu.privatregnskap.app.data.repository.LedgerSelectionRepository
import eu.privatregnskap.app.data.repository.PostingQueueRepository
import eu.privatregnskap.app.data.repository.TokenRepository
import eu.privatregnskap.app.data.repository.TransactionRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import javax.inject.Inject

data class AttachmentsUiState(
    val attachments: List<AttachmentResponse> = emptyList(),
    val isLoading: Boolean = false,
    val isUploading: Boolean = false,
    val extractingId: Int? = null,
    val error: String? = null,
    val requiresSubscription: Boolean = false
)

/** Account types an attachment may be posted against; see the web chart. */
val POSTING_ACCOUNT_GROUPS = listOf(
    "EXPENSE" to "Kostnad",
    "ASSET" to "Eiendel",
    "LIABILITY" to "Gjeld",
)

@HiltViewModel
class AttachmentsViewModel @Inject constructor(
    private val repository: AttachmentRepository,
    private val transactionRepository: TransactionRepository,
    private val postingQueueRepository: PostingQueueRepository,
    private val ledgerSelection: LedgerSelectionRepository,
    private val tokenRepository: TokenRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(AttachmentsUiState())
    val uiState: StateFlow<AttachmentsUiState> = _uiState.asStateFlow()

    private val _transactions = MutableStateFlow<List<TransactionResponse>>(emptyList())
    val transactions: StateFlow<List<TransactionResponse>> = _transactions.asStateFlow()

    private val _suggestedMatches = MutableStateFlow<List<MatchSuggestionResponse>>(emptyList())
    val suggestedMatches: StateFlow<List<MatchSuggestionResponse>> = _suggestedMatches.asStateFlow()

    // Accounts an invoice may be posted against, for the edit sheet
    private val _accounts = MutableStateFlow<List<AccountResponse>>(emptyList())
    val accounts: StateFlow<List<AccountResponse>> = _accounts.asStateFlow()

    // The plan an invoice produced, keyed by receipt id. It carries the
    // expected counter-account, which lives on the plan and not on the receipt.
    private val _plansByReceipt = MutableStateFlow<Map<Int, PlannedTransactionResponse>>(emptyMap())
    val plansByReceipt: StateFlow<Map<Int, PlannedTransactionResponse>> = _plansByReceipt.asStateFlow()

    private val _message = MutableSharedFlow<String>()
    val message = _message.asSharedFlow()

    // Pair<FileProvider URI, mimeType> — collected by screen to fire ACTION_VIEW intent
    private val _openFileEvent = MutableSharedFlow<Pair<Uri, String>>()
    val openFileEvent = _openFileEvent.asSharedFlow()

    // Local copy of a PDF being shown inside the app; null when the viewer is closed
    private val _pdfFile = MutableStateFlow<File?>(null)
    val pdfFile: StateFlow<File?> = _pdfFile.asStateFlow()

    // Triple<attachmentId, sourceUri, destUri> — collected by screen to launch uCrop
    private val _cropEditEvent = MutableSharedFlow<Triple<Int, Uri, Uri>>()
    val cropEditEvent = _cropEditEvent.asSharedFlow()

    private var currentLedgerId: Int? = null
    private var currentStatusFilter: String? = null
    private var currentSearch: String? = null

    init {
        viewModelScope.launch {
            ledgerSelection.ensureLoaded().onFailure {
                _uiState.value = AttachmentsUiState(error = "Kunne ikke laste regnskaper")
            }
            ledgerSelection.selectedLedgerId.collect { id ->
                currentLedgerId = id
                // Another ledger has another chart; keeping the old one would
                // offer accounts that do not exist here
                _accounts.value = emptyList()
                _plansByReceipt.value = emptyMap()
                loadAll()
            }
        }
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

            repository.getAttachments(currentLedgerId, statusFilter, search?.ifBlank { null }).fold(
                onSuccess = { list ->
                    _uiState.value = AttachmentsUiState(attachments = list)
                    loadPlans()
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

    private suspend fun downloadToCache(attachment: AttachmentResponse, context: Context): File {
        val url = imageUrl(attachment.id)
        val bytes = withContext(Dispatchers.IO) { java.net.URL(url).readBytes() }
        val ext = if (attachment.mimeType == "application/pdf") "pdf" else "jpg"
        val file = File(context.cacheDir, "attachment_${attachment.id}.$ext")
        withContext(Dispatchers.IO) { file.writeBytes(bytes) }
        return file
    }

    fun openPdfInApp(attachment: AttachmentResponse, context: Context) {
        viewModelScope.launch {
            try {
                _pdfFile.value = downloadToCache(attachment, context)
            } catch (e: Exception) {
                _message.emit("Kunne ikke hente PDF: ${e.message}")
            }
        }
    }

    fun closePdf() {
        _pdfFile.value = null
    }

    fun openAttachmentExternal(attachment: AttachmentResponse, context: Context) {
        viewModelScope.launch {
            try {
                val file = downloadToCache(attachment, context)
                val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
                _openFileEvent.emit(uri to (attachment.mimeType ?: "application/octet-stream"))
            } catch (e: Exception) {
                _message.emit("Kunne ikke åpne fil: ${e.message}")
            }
        }
    }

    fun prepareCropEdit(attachment: AttachmentResponse, context: Context) {
        if (attachment.mimeType == "application/pdf") return
        viewModelScope.launch {
            try {
                val url = imageUrl(attachment.id)
                val bytes = withContext(Dispatchers.IO) { java.net.URL(url).readBytes() }
                val srcFile = File(context.cacheDir, "crop_src_${attachment.id}.jpg")
                val destFile = File(context.cacheDir, "crop_dest_${attachment.id}.jpg")
                withContext(Dispatchers.IO) { srcFile.writeBytes(bytes) }
                val srcUri = FileProvider.getUriForFile(
                    context, "${context.packageName}.fileprovider", srcFile
                )
                _cropEditEvent.emit(Triple(attachment.id, srcUri, Uri.fromFile(destFile)))
            } catch (e: Exception) {
                _message.emit("Kunne ikke åpne editor: ${e.message}")
            }
        }
    }

    fun uploadCropped(attachmentId: Int, croppedUri: Uri, context: Context) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isUploading = true)
            try {
                val bytes = withContext(Dispatchers.IO) {
                    val path = croppedUri.path ?: throw Exception("Ugyldig fil")
                    File(path).readBytes()
                }
                repository.rotateAttachment(currentLedgerId, attachmentId, bytes).fold(
                    onSuccess = { _message.emit("Bilde lagret"); loadAll() },
                    onFailure = { _message.emit("Kunne ikke lagre: ${it.message}") }
                )
            } catch (e: Exception) {
                _message.emit("Feil: ${e.message}")
            } finally {
                _uiState.value = _uiState.value.copy(isUploading = false)
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
                val mimeType = contentResolver.getType(uri) ?: "application/octet-stream"

                // SAF URIs have a numeric lastPathSegment — query the actual display name
                val displayName = contentResolver.query(
                    uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null
                )?.use { cursor ->
                    if (cursor.moveToFirst()) cursor.getString(0) else null
                }
                val fileName = when {
                    !displayName.isNullOrBlank() -> displayName
                    mimeType == "application/pdf" -> "document.pdf"
                    else -> "attachment.jpg"
                }
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

    private suspend fun loadPlans() {
        repository.getPlannedTransactions(currentLedgerId).onSuccess { plans ->
            _plansByReceipt.value = plans
                .filter { it.receiptId != null }
                .associateBy { it.receiptId!! }
        }
    }

    /** Loaded on demand: only the edit sheet needs the chart of accounts. */
    fun ensureAccounts() {
        if (_accounts.value.isNotEmpty()) return
        viewModelScope.launch {
            postingQueueRepository.getAccounts(currentLedgerId).onSuccess { all ->
                val wanted = POSTING_ACCOUNT_GROUPS.map { it.first }.toSet()
                _accounts.value = all.filter { it.accountType in wanted }
            }
        }
    }

    /**
     * Save the attachment's own fields, then the expected counter-account.
     *
     * The account lives on the planned transaction, which the receipt update
     * may have only just created, so the plans are re-read in between. A
     * matched plan is left alone; the backend refuses to change it anyway.
     */
    fun saveEdit(
        id: Int,
        attachmentType: String,
        receiptDate: String?,
        dueDate: String?,
        amount: String?,
        description: String?,
        expectedAccountId: Int?
    ) {
        viewModelScope.launch {
            val result = repository.updateAttachment(
                currentLedgerId,
                id,
                ReceiptUpdateRequest(
                    attachmentType = attachmentType,
                    receiptDate = receiptDate,
                    dueDate = if (attachmentType == "INVOICE") dueDate else null,
                    amount = amount,
                    description = description
                )
            )
            result.fold(
                onSuccess = { updated ->
                    val list = _uiState.value.attachments.map { if (it.id == id) updated else it }
                    _uiState.value = _uiState.value.copy(attachments = list)
                    if (attachmentType == "INVOICE") {
                        loadPlans()
                        val plan = _plansByReceipt.value[id]
                        if (plan != null && plan.status != "MATCHED" &&
                            plan.suggestedAccountId != expectedAccountId
                        ) {
                            repository.setPlannedAccount(currentLedgerId, plan.id, expectedAccountId)
                            loadPlans()
                        }
                    }
                    _message.emit("Vedlegg lagret")
                },
                onFailure = { e -> _message.emit("Kunne ikke lagre: ${e.message}") }
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
