package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.BudgetReportResponse
import eu.privatregnskap.app.data.network.dto.BudgetResponse
import javax.inject.Inject
import javax.inject.Singleton

interface BudgetRepository {
    suspend fun getBudgets(ledgerId: Int?): Result<List<BudgetResponse>>
    suspend fun getBudgetReport(ledgerId: Int?, budgetId: Int): Result<BudgetReportResponse>
}

@Singleton
class BudgetRepositoryImpl @Inject constructor(
    private val apiService: ApiService
) : BudgetRepository {

    override suspend fun getBudgets(ledgerId: Int?): Result<List<BudgetResponse>> =
        runCatching { apiService.getBudgets(ledgerId) }

    override suspend fun getBudgetReport(ledgerId: Int?, budgetId: Int): Result<BudgetReportResponse> =
        runCatching { apiService.getBudgetReport(ledgerId, budgetId) }
}
