package eu.privatregnskap.app.data.network.dto

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class TokenResponse(
    @Json(name = "access_token") val accessToken: String,
    @Json(name = "token_type") val tokenType: String,
    @Json(name = "refresh_token") val refreshToken: String? = null
)

@JsonClass(generateAdapter = true)
data class RefreshRequest(
    @Json(name = "refresh_token") val refreshToken: String
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
data class BiometricTokenResponse(
    @Json(name = "refresh_token") val refreshToken: String
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

@JsonClass(generateAdapter = true)
data class PasskeyCredentialResponse(
    val id: Int,
    @Json(name = "credential_name") val credentialName: String?,
    @Json(name = "created_at") val createdAt: String,
    @Json(name = "last_used_at") val lastUsedAt: String?
)

@JsonClass(generateAdapter = true)
data class PasskeyRegisterBeginRequest(
    @Json(name = "credential_name") val credentialName: String?
)

@JsonClass(generateAdapter = true)
data class AttachmentResponse(
    val id: Int,
    @Json(name = "attachment_type") val attachmentType: String,
    @Json(name = "original_filename") val originalFilename: String?,
    @Json(name = "file_size") val fileSize: Int?,
    @Json(name = "mime_type") val mimeType: String?,
    @Json(name = "receipt_date") val receiptDate: String?,
    @Json(name = "due_date") val dueDate: String?,
    val amount: Double?,
    val description: String?,
    val status: String,
    @Json(name = "matched_transaction_id") val matchedTransactionId: Int?,
    @Json(name = "ai_extracted_vendor") val aiExtractedVendor: String?,
    @Json(name = "ai_extracted_description") val aiExtractedDescription: String?,
    @Json(name = "ai_extracted_amount") val aiExtractedAmount: Double?,
    @Json(name = "ai_extracted_date") val aiExtractedDate: String?,
    @Json(name = "ai_confidence") val aiConfidence: Double?,
    @Json(name = "ai_suggested_account") val aiSuggestedAccount: String?,
    @Json(name = "created_at") val createdAt: String
)

@JsonClass(generateAdapter = true)
data class BudgetDrilldownEntry(
    val id: Int,
    val date: String,
    val description: String,
    val status: String,
    val debit: Double,
    val credit: Double,
    val amount: Double
)

@JsonClass(generateAdapter = true)
data class MatchSuggestionResponse(
    val transaction: TransactionResponse,
    val score: Int,
    val reasons: List<String>
)

@JsonClass(generateAdapter = true)
data class BudgetResponse(
    val id: Int,
    val name: String,
    val year: Int
)

@JsonClass(generateAdapter = true)
data class BudgetMonthData(
    val month: Int,
    val budget: Double,
    val actual: Double,
    val variance: Double
)

@JsonClass(generateAdapter = true)
data class BudgetReportLine(
    @Json(name = "account_id") val accountId: Int,
    @Json(name = "account_number") val accountNumber: String,
    @Json(name = "account_name") val accountName: String,
    @Json(name = "account_type") val accountType: String,
    val months: List<BudgetMonthData>,
    @Json(name = "total_budget") val totalBudget: Double,
    @Json(name = "total_actual") val totalActual: Double,
    @Json(name = "total_variance") val totalVariance: Double
)

@JsonClass(generateAdapter = true)
data class BudgetReportResponse(
    val budget: BudgetResponse,
    val lines: List<BudgetReportLine>
)

// ─── Settlement ──────────────────────────────────────────────────────────────
// Monetary fields are serialised as decimal strings by the backend.

@JsonClass(generateAdapter = true)
data class SettlementTotals(
    val booked: String,
    @Json(name = "booked_fixed") val bookedFixed: String,
    @Json(name = "booked_variable") val bookedVariable: String,
    @Json(name = "excluded_booked") val excludedBooked: String,
    @Json(name = "planned_remaining") val plannedRemaining: String,
    @Json(name = "recurring_remaining") val recurringRemaining: String,
    @Json(name = "variable_remaining") val variableRemaining: String,
    @Json(name = "typical_variable_month") val typicalVariableMonth: String,
    @Json(name = "forecast_total") val forecastTotal: String
)

@JsonClass(generateAdapter = true)
data class SettlementPlannedLine(
    @Json(name = "planned_transaction_id") val plannedTransactionId: Int,
    @Json(name = "receipt_id") val receiptId: Int? = null,
    val description: String,
    @Json(name = "expected_date") val expectedDate: String,
    val amount: String,
    val overdue: Boolean
)

@JsonClass(generateAdapter = true)
data class SettlementRecurringLine(
    val key: String,
    val description: String,
    @Json(name = "expected_day") val expectedDay: Int,
    val amount: String,
    @Json(name = "period_months") val periodMonths: Int
)

@JsonClass(generateAdapter = true)
data class SettlementMemberResult(
    @Json(name = "user_id") val userId: Int,
    @Json(name = "full_name") val fullName: String,
    @Json(name = "share_percent") val sharePercent: String,
    @Json(name = "deposit_account_id") val depositAccountId: Int? = null,
    @Json(name = "share_amount") val shareAmount: String,
    @Json(name = "own_withdrawals") val ownWithdrawals: String,
    val contributed: String,
    @Json(name = "recommended_transfer") val recommendedTransfer: String
)

@JsonClass(generateAdapter = true)
data class SettlementCreditCard(
    @Json(name = "bank_account_id") val bankAccountId: Int,
    val name: String,
    @Json(name = "account_id") val accountId: Int,
    val owed: String
)

@JsonClass(generateAdapter = true)
data class SettlementLiquidity(
    @Json(name = "operating_balance") val operatingBalance: String? = null,
    @Json(name = "credit_cards") val creditCards: List<SettlementCreditCard>,
    @Json(name = "credit_card_owed_total") val creditCardOwedTotal: String
)

@JsonClass(generateAdapter = true)
data class SettlementCalculationResponse(
    @Json(name = "ledger_id") val ledgerId: Int,
    val month: String,
    @Json(name = "as_of") val asOf: String,
    @Json(name = "days_remaining") val daysRemaining: Int,
    @Json(name = "month_complete") val monthComplete: Boolean,
    @Json(name = "operating_account_id") val operatingAccountId: Int? = null,
    @Json(name = "excluded_account_ids") val excludedAccountIds: List<Int>,
    val totals: SettlementTotals,
    val planned: List<SettlementPlannedLine>,
    val recurring: List<SettlementRecurringLine>,
    val members: List<SettlementMemberResult>,
    val liquidity: SettlementLiquidity
)
