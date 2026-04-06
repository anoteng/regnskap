package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.BudgetDrilldownEntry
import eu.privatregnskap.app.data.network.dto.BudgetReportResponse
import eu.privatregnskap.app.data.network.dto.BudgetResponse
import javax.inject.Inject
import javax.inject.Singleton

interface BudgetRepository {
    suspend fun getBudgets(ledgerId: Int?): Result<List<BudgetResponse>>
    suspend fun getBudgetReport(ledgerId: Int?, budgetId: Int): Result<BudgetReportResponse>
    suspend fun getDrilldown(ledgerId: Int?, budgetId: Int, accountId: Int, month: Int?): Result<List<BudgetDrilldownEntry>>
}

@Singleton
class BudgetRepositoryImpl @Inject constructor(
    private val apiService: ApiService
) : BudgetRepository {

    override suspend fun getBudgets(ledgerId: Int?): Result<List<BudgetResponse>> =
        runCatching { apiService.getBudgets(ledgerId) }

    override suspend fun getBudgetReport(ledgerId: Int?, budgetId: Int): Result<BudgetReportResponse> =
        runCatching { apiService.getBudgetReport(ledgerId, budgetId) }

    override suspend fun getDrilldown(ledgerId: Int?, budgetId: Int, accountId: Int, month: Int?): Result<List<BudgetDrilldownEntry>> =
        runCatching { apiService.getBudgetDrilldown(ledgerId, budgetId, accountId, month) }
}
