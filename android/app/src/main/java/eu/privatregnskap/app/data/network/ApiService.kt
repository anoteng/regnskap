package eu.privatregnskap.app.data.network

import eu.privatregnskap.app.data.network.dto.AccountResponse
import eu.privatregnskap.app.data.network.dto.AttachmentResponse
import eu.privatregnskap.app.data.network.dto.ChainRequest
import eu.privatregnskap.app.data.network.dto.ChainSuggestionsResponse
import eu.privatregnskap.app.data.network.dto.LedgerResponse
import eu.privatregnskap.app.data.network.dto.PasskeyCredentialResponse
import eu.privatregnskap.app.data.network.dto.PasskeyRegisterBeginRequest
import eu.privatregnskap.app.data.network.dto.PasswordResetRequest
import eu.privatregnskap.app.data.network.dto.PostingQueueResponse
import eu.privatregnskap.app.data.network.dto.TokenResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.network.dto.UpdateTransactionRequest
import eu.privatregnskap.app.data.network.dto.UserResponse
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    // ─── Auth ────────────────────────────────────────────────────────────────

    @FormUrlEncoded
    @POST("auth/login")
    suspend fun login(
        @Field("username") username: String,
        @Field("password") password: String
    ): TokenResponse

    @POST("auth/refresh")
    suspend fun refresh(): TokenResponse

    @POST("auth/password-reset/request")
    suspend fun requestPasswordReset(@Body request: PasswordResetRequest): Map<String, String>

    @GET("auth/me")
    suspend fun getMe(): UserResponse

    // ─── Passkeys ─────────────────────────────────────────────────────────────

    @POST("auth/passkey/login/begin")
    suspend fun passkeyLoginBegin(@Body body: RequestBody): ResponseBody

    @POST("auth/passkey/login/complete")
    suspend fun passkeyLoginComplete(@Body body: RequestBody): TokenResponse

    @POST("auth/passkey/register/begin")
    suspend fun passkeyRegisterBegin(@Body body: PasskeyRegisterBeginRequest): ResponseBody

    @POST("auth/passkey/register/complete")
    suspend fun passkeyRegisterComplete(@Body body: RequestBody): ResponseBody

    @GET("auth/passkey/credentials")
    suspend fun listPasskeyCredentials(): List<PasskeyCredentialResponse>

    @DELETE("auth/passkey/credentials/{id}")
    suspend fun deletePasskeyCredential(@Path("id") id: Int): ResponseBody

    @PATCH("auth/passkey/credentials/{id}/rename")
    suspend fun renamePasskeyCredential(
        @Path("id") id: Int,
        @Query("new_name") newName: String
    ): PasskeyCredentialResponse

    // ─── Ledgers ──────────────────────────────────────────────────────────────

    @GET("ledgers/")
    suspend fun getLedgers(): List<LedgerResponse>

    // ─── Transactions ─────────────────────────────────────────────────────────

    @GET("transactions/")
    suspend fun getTransactions(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 50
    ): List<TransactionResponse>

    @GET("transactions/queue")
    suspend fun getPostingQueue(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 50
    ): PostingQueueResponse

    @POST("transactions/{id}/post")
    suspend fun postTransaction(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Path("id") id: Int
    ): ResponseBody

    @PUT("transactions/{id}")
    suspend fun updateTransaction(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Path("id") id: Int,
        @Body request: UpdateTransactionRequest
    ): TransactionResponse

    @DELETE("transactions/{id}")
    suspend fun deleteTransaction(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Path("id") id: Int
    ): ResponseBody

    @POST("transactions/chain")
    suspend fun chainTransactions(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Body request: ChainRequest
    ): ResponseBody

    // ─── Accounts ─────────────────────────────────────────────────────────────

    @GET("accounts/")
    suspend fun getAccounts(
        @Header("X-Ledger-ID") ledgerId: Int? = null
    ): List<AccountResponse>

    // ─── Attachments ──────────────────────────────────────────────────────────

    @GET("receipts/")
    suspend fun getAttachments(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Query("status") status: String? = null,
        @Query("q") search: String? = null
    ): List<AttachmentResponse>

    @Multipart
    @POST("receipts/upload")
    suspend fun uploadAttachment(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Part file: MultipartBody.Part,
        @Part("attachment_type") attachmentType: RequestBody,
        @Part("receipt_date") receiptDate: RequestBody? = null,
        @Part("due_date") dueDate: RequestBody? = null,
        @Part("amount") amount: RequestBody? = null,
        @Part("description") description: RequestBody? = null
    ): AttachmentResponse

    @DELETE("receipts/{id}")
    suspend fun deleteAttachment(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Path("id") id: Int
    ): ResponseBody

    @POST("receipts/{id}/extract")
    suspend fun extractAttachmentAI(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Path("id") id: Int
    ): AttachmentResponse

    @POST("receipts/{id}/match/{transactionId}")
    suspend fun matchAttachment(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Path("id") id: Int,
        @Path("transactionId") transactionId: Int
    ): ResponseBody

    @POST("receipts/{id}/unmatch")
    suspend fun unmatchAttachment(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Path("id") id: Int
    ): ResponseBody

    @GET("receipts/{id}/suggest-match")
    suspend fun getMatchSuggestions(
        @Header("X-Ledger-ID") ledgerId: Int? = null,
        @Path("id") id: Int
    ): List<MatchSuggestionResponse>

    // ─── Chain suggestions ────────────────────────────────────────────────────

    @GET("transactions/chain-suggestions")
    suspend fun getChainSuggestions(
        @Header("X-Ledger-ID") ledgerId: Int? = null
    ): ChainSuggestionsResponse
}
