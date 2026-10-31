package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import javax.inject.Inject
import javax.inject.Singleton

interface TransactionRepository {
    suspend fun getTransactions(
        ledgerId: Int? = null,
        skip: Int = 0,
        limit: Int = 50,
        search: String? = null
    ): Result<List<TransactionResponse>>

    suspend fun getTransaction(id: Int, ledgerId: Int? = null): Result<TransactionResponse>
}

@Singleton
class TransactionRepositoryImpl @Inject constructor(
    private val apiService: ApiService
) : TransactionRepository {

    override suspend fun getTransactions(
        ledgerId: Int?,
        skip: Int,
        limit: Int,
        search: String?
    ): Result<List<TransactionResponse>> {
        return try {
            val transactions = apiService.getTransactions(
                ledgerId = ledgerId,
                skip = skip,
                limit = limit,
                search = search?.ifBlank { null }
            )
            Result.success(transactions)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getTransaction(id: Int, ledgerId: Int?): Result<TransactionResponse> {
        return try {
            Result.success(apiService.getTransaction(ledgerId = ledgerId, id = id))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
