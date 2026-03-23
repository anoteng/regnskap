package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.LedgerResponse
import javax.inject.Inject
import javax.inject.Singleton

interface LedgerRepository {
    suspend fun getLedgers(): Result<List<LedgerResponse>>
}

@Singleton
class LedgerRepositoryImpl @Inject constructor(
    private val apiService: ApiService
) : LedgerRepository {
    override suspend fun getLedgers(): Result<List<LedgerResponse>> {
        return try {
            Result.success(apiService.getLedgers())
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
