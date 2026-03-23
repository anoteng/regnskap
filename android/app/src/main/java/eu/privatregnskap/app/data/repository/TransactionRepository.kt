package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import javax.inject.Inject
import javax.inject.Singleton

interface TransactionRepository {
    suspend fun getTransactions(ledgerId: Int? = null, skip: Int = 0, limit: Int = 50): Result<List<TransactionResponse>>
}

@Singleton
class TransactionRepositoryImpl @Inject constructor(
    private val apiService: ApiService
) : TransactionRepository {

    override suspend fun getTransactions(ledgerId: Int?, skip: Int, limit: Int): Result<List<TransactionResponse>> {
        return try {
            val transactions = apiService.getTransactions(
                ledgerId = ledgerId,
                skip = skip,
                limit = limit
            )
            Result.success(transactions)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
