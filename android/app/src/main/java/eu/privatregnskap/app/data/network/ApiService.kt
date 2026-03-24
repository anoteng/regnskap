package eu.privatregnskap.app.data.network

import eu.privatregnskap.app.data.network.dto.AccountResponse
import eu.privatregnskap.app.data.network.dto.ChainRequest
import eu.privatregnskap.app.data.network.dto.ChainSuggestionsResponse
import eu.privatregnskap.app.data.network.dto.LedgerResponse
import eu.privatregnskap.app.data.network.dto.PasswordResetRequest
import eu.privatregnskap.app.data.network.dto.PostingQueueResponse
import eu.privatregnskap.app.data.network.dto.TokenResponse
import eu.privatregnskap.app.data.network.dto.TransactionResponse
import eu.privatregnskap.app.data.network.dto.UpdateTransactionRequest
import eu.privatregnskap.app.data.network.dto.UserResponse
import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.PUT
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

    // ─── Chain suggestions ────────────────────────────────────────────────────

    @GET("transactions/chain-suggestions")
    suspend fun getChainSuggestions(
        @Header("X-Ledger-ID") ledgerId: Int? = null
    ): ChainSuggestionsResponse
}
