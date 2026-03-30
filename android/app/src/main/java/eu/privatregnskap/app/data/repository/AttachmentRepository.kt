package eu.privatregnskap.app.data.repository

import eu.privatregnskap.app.data.network.ApiService
import eu.privatregnskap.app.data.network.dto.AttachmentResponse
import eu.privatregnskap.app.data.network.dto.MatchSuggestionResponse
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject
import javax.inject.Singleton

interface AttachmentRepository {
    suspend fun getAttachments(ledgerId: Int?, status: String? = null, search: String? = null): Result<List<AttachmentResponse>>
    suspend fun uploadAttachment(
        ledgerId: Int?,
        fileBytes: ByteArray,
        fileName: String,
        mimeType: String,
        attachmentType: String,
        receiptDate: String?,
        dueDate: String?,
        amount: String?,
        description: String?
    ): Result<AttachmentResponse>
    suspend fun deleteAttachment(ledgerId: Int?, id: Int): Result<Unit>
    suspend fun extractAI(ledgerId: Int?, id: Int): Result<AttachmentResponse>
    suspend fun matchAttachment(ledgerId: Int?, id: Int, transactionId: Int): Result<Unit>
    suspend fun unmatchAttachment(ledgerId: Int?, id: Int): Result<Unit>
    suspend fun suggestMatches(ledgerId: Int?, id: Int): Result<List<MatchSuggestionResponse>>
    suspend fun rotateAttachment(ledgerId: Int?, id: Int, bytes: ByteArray): Result<Unit>
}

@Singleton
class AttachmentRepositoryImpl @Inject constructor(
    private val apiService: ApiService
) : AttachmentRepository {

    override suspend fun getAttachments(ledgerId: Int?, status: String?, search: String?): Result<List<AttachmentResponse>> =
        runCatching { apiService.getAttachments(ledgerId, status, search) }

    override suspend fun uploadAttachment(
        ledgerId: Int?,
        fileBytes: ByteArray,
        fileName: String,
        mimeType: String,
        attachmentType: String,
        receiptDate: String?,
        dueDate: String?,
        amount: String?,
        description: String?
    ): Result<AttachmentResponse> = runCatching {
        val filePart = MultipartBody.Part.createFormData(
            "file",
            fileName,
            fileBytes.toRequestBody(mimeType.toMediaType())
        )
        val typePart = attachmentType.toRequestBody("text/plain".toMediaType())
        val datePart = receiptDate?.toRequestBody("text/plain".toMediaType())
        val dueDatePart = dueDate?.toRequestBody("text/plain".toMediaType())
        val amountPart = amount?.toRequestBody("text/plain".toMediaType())
        val descPart = description?.toRequestBody("text/plain".toMediaType())

        apiService.uploadAttachment(ledgerId, filePart, typePart, datePart, dueDatePart, amountPart, descPart)
    }

    override suspend fun deleteAttachment(ledgerId: Int?, id: Int): Result<Unit> =
        runCatching { apiService.deleteAttachment(ledgerId, id); Unit }

    override suspend fun extractAI(ledgerId: Int?, id: Int): Result<AttachmentResponse> =
        runCatching { apiService.extractAttachmentAI(ledgerId, id) }

    override suspend fun matchAttachment(ledgerId: Int?, id: Int, transactionId: Int): Result<Unit> =
        runCatching { apiService.matchAttachment(ledgerId, id, transactionId); Unit }

    override suspend fun unmatchAttachment(ledgerId: Int?, id: Int): Result<Unit> =
        runCatching { apiService.unmatchAttachment(ledgerId, id); Unit }

    override suspend fun suggestMatches(ledgerId: Int?, id: Int): Result<List<MatchSuggestionResponse>> =
        runCatching { apiService.getMatchSuggestions(ledgerId, id) }

    override suspend fun rotateAttachment(ledgerId: Int?, id: Int, bytes: ByteArray): Result<Unit> =
        runCatching {
            val part = MultipartBody.Part.createFormData(
                "file", "cropped.jpg",
                bytes.toRequestBody("image/jpeg".toMediaType())
            )
            apiService.rotateAttachment(ledgerId, id, part)
            Unit
        }
}
