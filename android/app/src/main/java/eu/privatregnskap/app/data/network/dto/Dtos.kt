package eu.privatregnskap.app.data.network.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class TokenResponse(
    @Json(name = "access_token") val accessToken: String,
    @Json(name = "token_type") val tokenType: String
)

@JsonClass(generateAdapter = true)
data class UserResponse(
    val id: Int,
    val email: String,
    @Json(name = "full_name") val fullName: String,
    @Json(name = "is_active") val isActive: Boolean
)

@JsonClass(generateAdapter = true)
data class LedgerResponse(
    val id: Int,
    val name: String,
    @Json(name = "user_role") val userRole: String
)

@JsonClass(generateAdapter = true)
data class JournalEntryResponse(
    val id: Int,
    @Json(name = "account_id") val accountId: Int,
    @Json(name = "account_name") val accountName: String?,
    val debit: Double?,
    val credit: Double?
)

@JsonClass(generateAdapter = true)
data class TransactionResponse(
    val id: Int,
    val description: String,
    @Json(name = "transaction_date") val transactionDate: String,
    val reference: String?,
    val status: String,
    val source: String?,
    @Json(name = "is_reconciled") val isReconciled: Boolean,
    @Json(name = "journal_entries") val journalEntries: List<JournalEntryResponse> = emptyList()
)

@JsonClass(generateAdapter = true)
data class PasskeyLoginBeginRequest(
    val email: String?
)

@JsonClass(generateAdapter = true)
data class PasswordResetRequest(
    val email: String
)
