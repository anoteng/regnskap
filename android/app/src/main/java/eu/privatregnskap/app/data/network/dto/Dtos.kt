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
data class AccountInEntryDto(
    val id: Int,
    @Json(name = "account_number") val accountNumber: String,
    @Json(name = "account_name") val accountName: String,
    @Json(name = "account_type") val accountType: String
)

@JsonClass(generateAdapter = true)
data class JournalEntryResponse(
    val id: Int,
    @Json(name = "account_id") val accountId: Int,
    val account: AccountInEntryDto?,
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

@JsonClass(generateAdapter = true)
data class AccountResponse(
    val id: Int,
    @Json(name = "account_number") val accountNumber: String,
    @Json(name = "account_name") val accountName: String,
    @Json(name = "account_type") val accountType: String
)

@JsonClass(generateAdapter = true)
data class PostingQueueResponse(
    val transactions: List<TransactionResponse>,
    val total: Int,
    val skip: Int,
    val limit: Int
)

@JsonClass(generateAdapter = true)
data class ChainSuggestionDto(
    @Json(name = "primary_transaction_id") val primaryTransactionId: Int,
    @Json(name = "secondary_transaction_id") val secondaryTransactionId: Int,
    @Json(name = "primary_description") val primaryDescription: String,
    @Json(name = "secondary_description") val secondaryDescription: String,
    @Json(name = "primary_account_name") val primaryAccountName: String,
    @Json(name = "secondary_account_name") val secondaryAccountName: String,
    val amount: Double,
    @Json(name = "primary_date") val primaryDate: String,
    @Json(name = "secondary_date") val secondaryDate: String,
    val confidence: String
)

@JsonClass(generateAdapter = true)
data class ChainSuggestionsResponse(
    val suggestions: List<ChainSuggestionDto>,
    val total: Int
)

@JsonClass(generateAdapter = true)
data class ChainRequest(
    @Json(name = "primary_transaction_id") val primaryTransactionId: Int,
    @Json(name = "secondary_transaction_id") val secondaryTransactionId: Int,
    @Json(name = "auto_post") val autoPost: Boolean = false
)

@JsonClass(generateAdapter = true)
data class JournalEntryUpdate(
    @Json(name = "account_id") val accountId: Int,
    val debit: Double,
    val credit: Double
)

@JsonClass(generateAdapter = true)
data class UpdateTransactionRequest(
    @Json(name = "transaction_date") val transactionDate: String,
    val description: String,
    val reference: String?,
    @Json(name = "journal_entries") val journalEntries: List<JournalEntryUpdate>
)
