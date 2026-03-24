package eu.privatregnskap.app.ui.postingqueue

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import eu.privatregnskap.app.data.network.dto.AccountResponse
import eu.privatregnskap.app.data.network.dto.ChainRequest
import eu.privatregnskap.app.data.network.dto.ChainSuggestionDto
import eu.privatregnskap.app.data.network.dto.JournalEntryResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.network.dto.UpdateTransactionRequest
import eu.privatregnskap.app.data.repository.LedgerRepository
import eu.privatregnskap.app.data.repository.PostingQueueRepository
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PostingQueueUiState(
    val transactions: List<TransactionResponse> = emptyList(),
    val total: Int = 0,
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class PostingQueueViewModel @Inject constructor(
    private val repository: PostingQueueRepository,
    private val ledgerRepository: LedgerRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(PostingQueueUiState())
    val uiState: StateFlow<PostingQueueUiState> = _uiState.asStateFlow()

    private val _accounts = MutableStateFlow<List<AccountResponse>>(emptyList())
    val accounts: StateFlow<List<AccountResponse>> = _accounts.asStateFlow()

    private val _chainSuggestions = MutableStateFlow<List<ChainSuggestionDto>>(emptyList())
    val chainSuggestions: StateFlow<List<ChainSuggestionDto>> = _chainSuggestions.asStateFlow()

    private val _message = MutableSharedFlow<String>()
    val message = _message.asSharedFlow()

    private var currentLedgerId: Int? = null

    init {
        loadAll()
    }

    fun loadAll() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            if (currentLedgerId == null) {
                ledgerRepository.getLedgers().onSuccess { list ->
                    currentLedgerId = list.firstOrNull()?.id
                }.onFailure {
                    _uiState.value = PostingQueueUiState(
                        error = it.message ?: "Kunne ikke laste regnskaper"
                    )
                    return@launch
                }
            }

            val lid = currentLedgerId

            repository.getQueue(lid).fold(
                onSuccess = { response ->
                    _uiState.value = PostingQueueUiState(
                        transactions = response.transactions,
                        total = response.total
                    )
                },
                onFailure = {
                    _uiState.value = PostingQueueUiState(
                        error = it.message ?: "Kunne ikke laste posteringskøen"
                    )
                }
            )

            // Load accounts and chain suggestions in background
            launch {
                repository.getAccounts(lid).onSuccess { _accounts.value = it }
            }
            launch {
                repository.getChainSuggestions(lid).onSuccess {
                    _chainSuggestions.value = it.suggestions
                }
            }
        }
    }

    fun postTransaction(id: Int) {
        viewModelScope.launch {
            repository.postTransaction(currentLedgerId, id).fold(
                onSuccess = {
                    _message.emit("Transaksjon postert")
                    loadAll()
                },
                onFailure = { _message.emit("Feil: ${it.message}") }
            )
        }
    }

    fun postAllTransactions() {
        viewModelScope.launch {
            val balanced = _uiState.value.transactions.filter { it.isBalanced() }
            if (balanced.isEmpty()) return@launch

            var posted = 0
            var failed = 0
            for (t in balanced) {
                repository.postTransaction(currentLedgerId, t.id).fold(
                    onSuccess = { posted++ },
                    onFailure = { failed++ }
                )
            }
            val msg = "$posted postert${if (failed > 0) ", $failed feilet" else ""}"
            _message.emit(msg)
            loadAll()
        }
    }

    fun deleteTransaction(id: Int) {
        viewModelScope.launch {
            repository.deleteTransaction(currentLedgerId, id).fold(
                onSuccess = {
                    _message.emit("Transaksjon slettet")
                    loadAll()
                },
                onFailure = { _message.emit("Feil: ${it.message}") }
            )
        }
    }

    fun updateTransaction(id: Int, request: UpdateTransactionRequest) {
        viewModelScope.launch {
            repository.updateTransaction(currentLedgerId, id, request).fold(
                onSuccess = {
                    _message.emit("Transaksjon oppdatert")
                    loadAll()
                },
                onFailure = { _message.emit("Feil: ${it.message}") }
            )
        }
    }

    fun chainTransactions(primaryId: Int, secondaryId: Int, autoPost: Boolean) {
        viewModelScope.launch {
            repository.chainTransactions(
                currentLedgerId,
                ChainRequest(primaryId, secondaryId, autoPost)
            ).fold(
                onSuccess = {
                    _message.emit(if (autoPost) "Kjedet og postert" else "Transaksjoner kjedet")
                    loadAll()
                },
                onFailure = { _message.emit("Feil: ${it.message}") }
            )
        }
    }
}

fun TransactionResponse.isBalanced(): Boolean {
    val totalDebit = journalEntries.sumOf { it.debit ?: 0.0 }
    val totalCredit = journalEntries.sumOf { it.credit ?: 0.0 }
    return kotlin.math.abs(totalDebit - totalCredit) < 0.01 && journalEntries.size >= 2
}

fun TransactionResponse.totalAmount(): Double =
    journalEntries.maxOfOrNull { maxOf(it.debit ?: 0.0, it.credit ?: 0.0) } ?: 0.0

fun JournalEntryResponse.displayName(): String =
    account?.let { "${it.accountNumber} ${it.accountName}" } ?: accountId.toString()
