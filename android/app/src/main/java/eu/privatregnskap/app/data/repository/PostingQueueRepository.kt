package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.AccountResponse
import eu.privatregnskap.app.data.network.dto.ChainRequest
import eu.privatregnskap.app.data.network.dto.ChainSuggestionsResponse
import eu.privatregnskap.app.data.network.dto.PostingQueueResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.network.dto.UpdateTransactionRequest
import javax.inject.Inject
import javax.inject.Singleton

interface PostingQueueRepository {
    suspend fun getQueue(ledgerId: Int?, skip: Int = 0, limit: Int = 100): Result<PostingQueueResponse>
    suspend fun getAccounts(ledgerId: Int?): Result<List<AccountResponse>>
    suspend fun getChainSuggestions(ledgerId: Int?): Result<ChainSuggestionsResponse>
    suspend fun postTransaction(ledgerId: Int?, id: Int): Result<Unit>
    suspend fun deleteTransaction(ledgerId: Int?, id: Int): Result<Unit>
    suspend fun updateTransaction(ledgerId: Int?, id: Int, request: UpdateTransactionRequest): Result<TransactionResponse>
    suspend fun chainTransactions(ledgerId: Int?, request: ChainRequest): Result<Unit>
}

@Singleton
class PostingQueueRepositoryImpl @Inject constructor(
    private val apiService: ApiService
) : PostingQueueRepository {

    override suspend fun getQueue(ledgerId: Int?, skip: Int, limit: Int): Result<PostingQueueResponse> =
        runCatching { apiService.getPostingQueue(ledgerId, skip, limit) }

    override suspend fun getAccounts(ledgerId: Int?): Result<List<AccountResponse>> =
        runCatching { apiService.getAccounts(ledgerId) }

    override suspend fun getChainSuggestions(ledgerId: Int?): Result<ChainSuggestionsResponse> =
        runCatching { apiService.getChainSuggestions(ledgerId) }

    override suspend fun postTransaction(ledgerId: Int?, id: Int): Result<Unit> =
        runCatching {
            apiService.postTransaction(ledgerId, id)
            Unit
        }

    override suspend fun deleteTransaction(ledgerId: Int?, id: Int): Result<Unit> =
        runCatching {
            apiService.deleteTransaction(ledgerId, id)
            Unit
        }

    override suspend fun updateTransaction(
        ledgerId: Int?,
        id: Int,
        request: UpdateTransactionRequest
    ): Result<TransactionResponse> =
        runCatching { apiService.updateTransaction(ledgerId, id, request) }

    override suspend fun chainTransactions(ledgerId: Int?, request: ChainRequest): Result<Unit> =
        runCatching {
            apiService.chainTransactions(ledgerId, request)
            Unit
        }
}
