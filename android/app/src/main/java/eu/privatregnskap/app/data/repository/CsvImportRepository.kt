package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.BankAccountResponse
import eu.privatregnskap.app.data.network.dto.CsvImportResultResponse
import eu.privatregnskap.app.data.network.dto.CsvMappingResponse
import eu.privatregnskap.app.data.network.dto.CsvPreviewResponse
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject
import javax.inject.Singleton

interface CsvImportRepository {
    suspend fun getBankAccounts(ledgerId: Int?): Result<List<BankAccountResponse>>
    suspend fun getMappings(ledgerId: Int?): Result<List<CsvMappingResponse>>
    suspend fun preview(fileName: String, bytes: ByteArray, delimiter: String): Result<CsvPreviewResponse>
    suspend fun import(
        ledgerId: Int?,
        bankAccountId: Int,
        fileName: String,
        bytes: ByteArray,
        mappingConfigJson: String
    ): Result<CsvImportResultResponse>
}

@Singleton
class CsvImportRepositoryImpl @Inject constructor(
    private val apiService: ApiService
) : CsvImportRepository {

    private fun filePart(fileName: String, bytes: ByteArray) =
        MultipartBody.Part.createFormData("file", fileName, bytes.toRequestBody(CSV_MEDIA_TYPE))

    override suspend fun getBankAccounts(ledgerId: Int?): Result<List<BankAccountResponse>> =
        runCatching { apiService.getBankAccounts(ledgerId) }

    override suspend fun getMappings(ledgerId: Int?): Result<List<CsvMappingResponse>> =
        runCatching { apiService.getCsvMappings(ledgerId) }

    override suspend fun preview(
        fileName: String,
        bytes: ByteArray,
        delimiter: String
    ): Result<CsvPreviewResponse> = runCatching {
        apiService.csvPreview(
            file = filePart(fileName, bytes),
            delimiter = delimiter.toRequestBody(TEXT_MEDIA_TYPE)
        )
    }

    override suspend fun import(
        ledgerId: Int?,
        bankAccountId: Int,
        fileName: String,
        bytes: ByteArray,
        mappingConfigJson: String
    ): Result<CsvImportResultResponse> = runCatching {
        apiService.importCsv(
            ledgerId = ledgerId,
            bankAccountId = bankAccountId,
            file = filePart(fileName, bytes),
            mappingConfig = mappingConfigJson.toRequestBody(TEXT_MEDIA_TYPE)
        )
    }

    private companion object {
        val CSV_MEDIA_TYPE = "text/csv".toMediaType()
        val TEXT_MEDIA_TYPE = "text/plain".toMediaType()
    }
}
