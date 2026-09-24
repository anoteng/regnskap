package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.SettlementCalculationResponse
import eu.privatregnskap.app.data.network.dto.SettlementSettingsRequest
import eu.privatregnskap.app.data.network.dto.SettlementSettingsResponse
import retrofit2.HttpException
import javax.inject.Inject
import javax.inject.Singleton

interface SettlementRepository {
    /**
     * Settlement for the given month ("YYYY-MM", null = current). Success with
     * null means the feature is not enabled for the ledger.
     */
    suspend fun getCalculation(ledgerId: Int?, month: String?): Result<SettlementCalculationResponse?>

    suspend fun getSettings(ledgerId: Int?): Result<SettlementSettingsResponse>

    suspend fun updateSettings(
        ledgerId: Int?,
        settings: SettlementSettingsRequest
    ): Result<SettlementSettingsResponse>
}

@Singleton
class SettlementRepositoryImpl @Inject constructor(
    private val apiService: ApiService
) : SettlementRepository {

    override suspend fun getCalculation(ledgerId: Int?, month: String?): Result<SettlementCalculationResponse?> =
        runCatching<SettlementCalculationResponse?> { apiService.getSettlementCalculation(ledgerId, month) }
            .recoverCatching { e ->
                if (e is HttpException && e.code() == 409) null else throw e
            }

    override suspend fun getSettings(ledgerId: Int?): Result<SettlementSettingsResponse> =
        runCatching { apiService.getSettlementSettings(ledgerId) }

    override suspend fun updateSettings(
        ledgerId: Int?,
        settings: SettlementSettingsRequest
    ): Result<SettlementSettingsResponse> =
        runCatching { apiService.updateSettlementSettings(ledgerId, settings) }
}
