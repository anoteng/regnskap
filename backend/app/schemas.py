from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict
from datetime import date, datetime
from decimal import Decimal


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    email: Optional[str] = None


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    last_active_ledger_id: Optional[int] = None

    class Config:
        from_attributes = True


# Chart of Accounts Templates
class ChartOfAccountsTemplateBase(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    is_active: bool = True
    is_default: bool = False


class ChartOfAccountsTemplateCreate(ChartOfAccountsTemplateBase):
    pass


class ChartOfAccountsTemplate(ChartOfAccountsTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateAccountBase(BaseModel):
    account_number: str
    account_name: str
    account_type: str
    parent_account_number: Optional[str] = None
    description: Optional[str] = None
    is_default: bool = True
    sort_order: int = 0


class TemplateAccountCreate(TemplateAccountBase):
    template_id: int


class TemplateAccount(TemplateAccountBase):
    id: int
    template_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Ledgers
class LedgerBase(BaseModel):
    name: str


class BankAccountSetup(BaseModel):
    name: str
    account_type: str  # CHECKING, SAVINGS, CREDIT_CARD
    account_number: Optional[str] = None


class LedgerCreate(LedgerBase):
    chart_template_id: Optional[int] = None
    bank_accounts: Optional[List[BankAccountSetup]] = None


class Ledger(LedgerBase):
    id: int
    created_by: int
    chart_template_id: Optional[int] = None
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class LedgerWithRole(Ledger):
    user_role: str  # OWNER, MEMBER, VIEWER


class LedgerMemberBase(BaseModel):
    user_id: int
    role: str  # OWNER, MEMBER, VIEWER


class LedgerMemberCreate(BaseModel):
    email: EmailStr  # Invite by email
    role: str


class LedgerMember(LedgerMemberBase):
    ledger_id: int
    joined_at: datetime
    user: User  # Include user details

    class Config:
        from_attributes = True


class AccountBase(BaseModel):
    account_number: str
    account_name: str
    account_type: str


class AccountCreate(AccountBase):
    parent_account_id: Optional[int] = None
    value_change_account_id: Optional[int] = None
    description: Optional[str] = None
    # AVAILABLE, LOCKED, EXCLUDED or IGNORED; None means never classified
    fire_role: Optional[str] = None
    fire_unlock_age: Optional[int] = None
    # Years a pension pot is paid out over from the unlock age; None is a lump
    fire_payout_years: Optional[int] = None
    # Earmarked yearly deposit, taken out of the general savings rate
    fire_annual_contribution: Optional[Decimal] = None
    wealth_valuation_percent: Optional[Decimal] = None


class Account(AccountBase):
    id: int
    ledger_id: int
    parent_account_id: Optional[int] = None
    value_change_account_id: Optional[int] = None
    fire_role: Optional[str] = None
    fire_unlock_age: Optional[int] = None
    # Years a pension pot is paid out over from the unlock age; None is a lump
    fire_payout_years: Optional[int] = None
    # Earmarked yearly deposit, taken out of the general savings rate
    fire_annual_contribution: Optional[Decimal] = None
    wealth_valuation_percent: Optional[Decimal] = None
    is_active: bool
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BankAccountBase(BaseModel):
    name: str
    account_type: str
    account_number: Optional[str] = None


class BankAccountCreate(BankAccountBase):
    account_id: int


class BankAccountUpdate(BaseModel):
    name: Optional[str] = None
    account_type: Optional[str] = None
    account_number: Optional[str] = None
    account_id: Optional[int] = None
    opening_balance: Optional[Decimal] = None  # Sets IB transaction for year start


class BankAccount(BankAccountBase):
    id: int
    ledger_id: int
    account_id: int
    balance: Decimal
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class JournalEntryBase(BaseModel):
    account_id: int
    debit: float = Field(default=0.0, ge=0)
    credit: float = Field(default=0.0, ge=0)
    description: Optional[str] = None


class JournalEntryCreate(JournalEntryBase):
    pass


class JournalEntry(JournalEntryBase):
    id: int
    transaction_id: int
    created_at: datetime
    account: Optional['Account'] = None

    class Config:
        from_attributes = True


class TransactionBase(BaseModel):
    transaction_date: date
    description: str
    reference: Optional[str] = None


class TransactionCreate(TransactionBase):
    journal_entries: List[JournalEntryCreate]
    category_ids: List[int] = []
    status: Optional[str] = 'POSTED'


class Transaction(TransactionBase):
    id: int
    ledger_id: int
    created_by: Optional[int] = None
    is_reconciled: bool
    status: str  # DRAFT, POSTED, RECONCILED
    source: Optional[str] = None  # MANUAL, CSV_IMPORT, BANK_SYNC
    source_reference: Optional[str] = None  # External transaction ID if from bank sync
    created_at: datetime
    journal_entries: List[JournalEntry] = []

    class Config:
        from_attributes = True


class MarketValueRequest(BaseModel):
    """What the account is worth on a given date, not the change itself."""
    value: Decimal
    as_of: Optional[date] = None


class MarketValueEntry(BaseModel):
    """One dated adjustment, for showing the ups and downs over time."""
    transaction_id: int
    as_of: date
    value: Decimal
    change: Decimal
    counter_account_number: Optional[str] = None
    counter_account_name: Optional[str] = None


class OpeningBalanceRequest(BaseModel):
    """A positive amount sits on the account's natural side; negative flips it."""
    amount: Decimal
    as_of: Optional[date] = None


class PostingSuggestion(BaseModel):
    account_id: int
    account_number: str
    account_name: str
    times_used: int
    last_used: date


class PaginatedTransactions(BaseModel):
    transactions: List[Transaction]
    total: int
    skip: int
    limit: int
    # Keyed by transaction id. Empty for endpoints that don't compute them,
    # so adding this never changes an existing response shape.
    suggestions: Dict[str, List[PostingSuggestion]] = {}


class CategoryBase(BaseModel):
    name: str
    color: Optional[str] = None
    icon: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class Category(CategoryBase):
    id: int
    ledger_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BudgetLineBase(BaseModel):
    account_id: int
    period: int  # 1-12
    amount: Decimal


class BudgetLineCreate(BudgetLineBase):
    pass


class BudgetLine(BudgetLineBase):
    id: int
    budget_id: int

    class Config:
        from_attributes = True


class BudgetBase(BaseModel):
    name: str
    year: int


class BudgetCreate(BudgetBase):
    pass


class Budget(BudgetBase):
    id: int
    ledger_id: int
    created_by: int
    created_at: datetime
    lines: List['BudgetLine'] = []
    account_filter_ids: List[int] = []

    class Config:
        from_attributes = True


class BudgetLineInput(BaseModel):
    """Input for setting budget amounts for an account"""
    account_id: int
    distribution_type: str  # 'same', 'total', or 'manual'
    amount: Optional[Decimal] = None  # For 'same' or 'total'
    monthly_amounts: Optional[List[Decimal]] = None  # For 'manual' (12 values)


class CSVMappingBase(BaseModel):
    name: str
    date_column: str
    description_column: str
    amount_column: str
    reference_column: Optional[str] = None
    date_format: str = "YYYY-MM-DD"
    decimal_separator: str = "."
    delimiter: str = ","
    invert_amount: bool = False
    skip_rows: int = 0


class CSVMappingCreate(CSVMappingBase):
    pass


class CSVMapping(CSVMappingBase):
    id: int
    ledger_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BalanceSheetItem(BaseModel):
    account_number: str
    account_name: str
    balance: Decimal


class BalanceSheet(BaseModel):
    assets: List[BalanceSheetItem]
    liabilities: List[BalanceSheetItem]
    equity: List[BalanceSheetItem]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal


class IncomeStatementItem(BaseModel):
    account_number: str
    account_name: str
    amount: Decimal


class IncomeStatement(BaseModel):
    revenues: List[IncomeStatementItem]
    expenses: List[IncomeStatementItem]
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal


class ReceiptBase(BaseModel):
    attachment_type: str = "RECEIPT"
    receipt_date: Optional[date] = None
    due_date: Optional[date] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None


class ReceiptCreate(ReceiptBase):
    pass


class Receipt(ReceiptBase):
    id: int
    ledger_id: int
    uploaded_by: int
    original_filename: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    status: str
    matched_transaction_id: Optional[int] = None
    matched_at: Optional[datetime] = None
    matched_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    # AI extraction results
    ai_extracted_date: Optional[date] = None
    ai_extracted_amount: Optional[Decimal] = None
    ai_extracted_vendor: Optional[str] = None
    ai_extracted_description: Optional[str] = None
    ai_suggested_account: Optional[str] = None
    ai_confidence: Optional[Decimal] = None
    ai_processed_at: Optional[datetime] = None
    ai_processing_error: Optional[str] = None

    class Config:
        from_attributes = True


class PlannedTransaction(BaseModel):
    id: int
    ledger_id: int
    receipt_id: Optional[int] = None
    description: str
    expected_date: date
    amount: Decimal
    suggested_account_id: Optional[int] = None
    status: str
    matched_transaction_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlannedTransactionUpdate(BaseModel):
    suggested_account_id: Optional[int] = None
    description: Optional[str] = None
    expected_date: Optional[date] = None
    amount: Optional[Decimal] = None


class SettlementMemberInput(BaseModel):
    user_id: int
    share_percent: Decimal
    deposit_account_id: Optional[int] = None


class SettlementSettingsUpdate(BaseModel):
    is_enabled: bool = False
    operating_account_id: Optional[int] = None
    variable_lookback_months: int = 3
    carry_start: Optional[date] = None
    card_due_day: int = 15
    members: List[SettlementMemberInput] = []
    excluded_account_ids: List[int] = []


class SettlementMemberOut(BaseModel):
    user_id: int
    full_name: str
    email: str
    share_percent: Decimal
    deposit_account_id: Optional[int] = None


class SettlementSettingsOut(BaseModel):
    ledger_id: int
    is_enabled: bool
    operating_account_id: Optional[int] = None
    variable_lookback_months: int
    carry_start: Optional[date] = None
    card_due_day: int = 15
    members: List[SettlementMemberOut]
    excluded_account_ids: List[int]
    updated_at: Optional[datetime] = None


class SettlementTotals(BaseModel):
    booked: Decimal
    booked_fixed: Decimal
    booked_variable: Decimal
    excluded_booked: Decimal
    planned_remaining: Decimal
    recurring_remaining: Decimal
    variable_remaining: Decimal
    typical_variable_month: Decimal
    # Netted off the split: the shared account earned these itself
    income_booked: Decimal = Decimal("0")
    # Added to the split: not a cost, but cash that has to leave the account
    debt_principal: Decimal = Decimal("0")
    forecast_total: Decimal


class SettlementPlannedLine(BaseModel):
    planned_transaction_id: int
    receipt_id: Optional[int] = None
    description: str
    expected_date: date
    amount: Decimal
    overdue: bool


class SettlementCardStatement(SettlementPlannedLine):
    """A registered credit card invoice, held out of the cost base.

    Same shape as a planned line, reported separately so the figure is visible
    rather than silently dropped.
    """


class SettlementRecurringLine(BaseModel):
    key: str
    description: str
    expected_day: int
    amount: Decimal
    period_months: int


class SettlementMemberResult(BaseModel):
    user_id: int
    full_name: str
    share_percent: Decimal
    deposit_account_id: Optional[int] = None
    share_amount: Decimal
    own_withdrawals: Decimal
    contributed: Decimal
    # Running over- or underpayment from closed months; positive means the
    # member is ahead and owes less now
    carry_in: Decimal = Decimal("0")
    recommended_transfer: Decimal


class SettlementCreditCard(BaseModel):
    bank_account_id: int
    name: str
    account_id: int
    owed: Decimal


class SettlementLiquidity(BaseModel):
    operating_balance: Optional[Decimal] = None
    credit_cards: List[SettlementCreditCard]
    credit_card_owed_total: Decimal
    # What the card company has invoiced, when a statement is registered; the
    # owed total above also holds purchases made since the statement closed
    card_invoiced: Decimal = Decimal("0")
    open_invoices: Decimal = Decimal("0")
    outstanding_contributions: Decimal = Decimal("0")
    # Balance plus what is still to come in, less the card and the invoices
    expected_available: Optional[Decimal] = None
    covers_card: Optional[bool] = None
    card_due_day: int = 15


class SettlementCalculation(BaseModel):
    ledger_id: int
    month: str
    as_of: date
    days_remaining: int
    month_complete: bool
    operating_account_id: Optional[int] = None
    excluded_account_ids: List[int]
    carry_from: Optional[date] = None
    totals: SettlementTotals
    planned: List[SettlementPlannedLine]
    card_statements: List[SettlementCardStatement] = []
    recurring: List[SettlementRecurringLine]
    members: List[SettlementMemberResult]
    liquidity: SettlementLiquidity


class AiKeyStatus(BaseModel):
    configured: bool
    hint: Optional[str] = None
    """Last four characters, so the user can tell which key is stored."""


class AiKeyUpdate(BaseModel):
    api_key: str


# WebAuthn / Passkey schemas
class WebAuthnRegistrationStart(BaseModel):
    credential_name: Optional[str] = None


class WebAuthnRegistrationComplete(BaseModel):
    credential_name: Optional[str] = None
    attestation: dict


class WebAuthnLoginStart(BaseModel):
    email: Optional[EmailStr] = None


class WebAuthnLoginComplete(BaseModel):
    credential_id: str
    assertion: dict


class WebAuthnCredential(BaseModel):
    id: int
    credential_name: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Password Reset schemas
class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetResponse(BaseModel):
    message: str
    has_passkey: bool


class PasswordResetComplete(BaseModel):
    token: str
    new_password: str


# Bank Integration schemas

class BankProviderBase(BaseModel):
    name: str
    display_name: str
    environment: str  # SANDBOX or PRODUCTION
    authorization_url: Optional[str] = None
    token_url: Optional[str] = None
    api_base_url: Optional[str] = None
    config_notes: Optional[str] = None


class BankProviderCreate(BankProviderBase):
    config_data: Optional[str] = None  # JSON string


class BankProviderUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    environment: Optional[str] = None
    config_data: Optional[str] = None
    authorization_url: Optional[str] = None
    token_url: Optional[str] = None
    api_base_url: Optional[str] = None
    config_notes: Optional[str] = None


class BankProvider(BankProviderBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BankConnectionBase(BaseModel):
    external_account_name: Optional[str] = None
    external_account_iban: Optional[str] = None


class BankConnectionCreate(BaseModel):
    bank_account_id: int
    provider_id: int
    external_bank_id: Optional[str] = None  # For provider bank selection
    initial_sync_from_date: Optional[date] = None  # Limit historical data for initial sync


class AccountSelectionRequest(BaseModel):
    state_token: str
    selected_account_id: str
    bank_account_id: int


class BankConnection(BankConnectionBase):
    id: int
    ledger_id: int
    bank_account_id: int
    provider_id: int
    external_bank_id: Optional[str] = None
    external_account_id: str
    external_account_iban: Optional[str] = None
    external_account_bic: Optional[str] = None
    status: str
    connection_error: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    last_successful_sync_at: Optional[datetime] = None
    auto_sync_enabled: bool
    is_push: bool = False
    created_at: datetime
    created_by: int

    class Config:
        from_attributes = True


class PushConnectionCreate(BaseModel):
    bank_account_id: int
    external_account_id: str = Field(min_length=1, max_length=255)  # Account number at the bank
    external_account_name: Optional[str] = Field(None, max_length=255)
    external_bank_id: Optional[str] = Field(None, max_length=255)
    initial_sync_from_date: Optional[date] = None


class PushConnection(BaseModel):
    id: int
    bank_account_id: int
    bank_account_name: Optional[str] = None
    external_bank_id: Optional[str] = None
    external_account_id: str
    external_account_name: Optional[str] = None
    status: str
    connection_error: Optional[str] = None
    initial_sync_from_date: Optional[date] = None
    last_successful_sync_at: Optional[datetime] = None


class PushedTransaction(BaseModel):
    """One booked transaction, as the user's device read it from the bank.

    The amount keeps the bank's sign: positive into the account, negative out.
    """
    external_id: str = Field(min_length=1, max_length=255)
    transaction_date: date
    booking_date: Optional[date] = None
    value_date: Optional[date] = None
    amount: Decimal = Field(max_digits=15, decimal_places=2)
    currency: str = Field("NOK", min_length=3, max_length=3)
    description: str = Field("", max_length=2000)
    reference: Optional[str] = Field(None, max_length=255)
    merchant_name: Optional[str] = Field(None, max_length=255)
    raw_data: Optional[Dict] = None


class PushUpload(BaseModel):
    transactions: List[PushedTransaction] = Field(max_length=2000)


class BankTransactionBase(BaseModel):
    transaction_date: date
    amount: Decimal
    description: Optional[str] = None


class BankTransaction(BankTransactionBase):
    id: int
    bank_connection_id: int
    external_transaction_id: str
    booking_date: Optional[date] = None
    value_date: Optional[date] = None
    currency: str
    reference: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_category: Optional[str] = None
    import_status: str
    imported_transaction_id: Optional[int] = None
    fetched_at: datetime

    class Config:
        from_attributes = True


class BankSyncLogBase(BaseModel):
    sync_type: str
    sync_from_date: Optional[date] = None
    sync_to_date: Optional[date] = None


class BankSyncLog(BankSyncLogBase):
    id: int
    bank_connection_id: int
    sync_status: str
    transactions_fetched: int
    transactions_imported: int
    transactions_duplicate: int
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    triggered_by: Optional[int] = None

    class Config:
        from_attributes = True


class ChainSuggestion(BaseModel):
    primary_transaction_id: int
    secondary_transaction_id: int
    primary_description: str
    secondary_description: str
    primary_account_name: str
    secondary_account_name: str
    amount: Decimal
    primary_date: date
    secondary_date: date
    confidence: str  # HIGH or MEDIUM


class ChainSuggestionsResponse(BaseModel):
    suggestions: List[ChainSuggestion]
    total: int


class ChainTransactionsRequest(BaseModel):
    primary_transaction_id: int
    secondary_transaction_id: int
    auto_post: bool = False


class SyncParams(BaseModel):
    from_date: Optional[date] = None
    to_date: Optional[date] = None


class SyncResponse(BaseModel):
    status: str
    transactions_fetched: int
    imported: int
    duplicates: int
    message: Optional[str] = None


class OAuthInitiateResponse(BaseModel):
    authorization_url: str
    state_token: str


# Rebuild models to resolve forward references
JournalEntry.model_rebuild()


# ---------------------------------------------------------------------------
# FIRE
# ---------------------------------------------------------------------------

class FireObligationInput(BaseModel):
    """A cost with an end date. Give either monthly + end_date, or, for a
    loan, balance + interest_percent and let the payoff date be amortised."""
    id: Optional[int] = None
    name: str
    kind: str = "OTHER"
    """Where the remaining balance is read from, for a loan."""
    account_id: Optional[int] = None
    """Where the cost is already booked, and so left out of the spending base."""
    cost_account_id: Optional[int] = None
    monthly_amount: Decimal = Decimal("0")
    balance: Optional[Decimal] = None
    interest_percent: Optional[Decimal] = None
    end_date: Optional[date] = None
    inflation_adjusted: bool = False
    frees_up_cash: bool = True
    counts_as_debt: bool = True
    is_active: bool = True


class FireObligationOut(FireObligationInput):
    id: int

    class Config:
        from_attributes = True


class FireSettingsUpdate(BaseModel):
    is_enabled: bool = False
    birth_date: Optional[date] = None
    horizon_age: int = 95
    target_retirement_date: Optional[date] = None
    swr_percent: Decimal = Decimal("4.00")
    inflation_percent: Decimal = Decimal("2.50")
    expected_return_percent: Decimal = Decimal("7.00")
    return_volatility_percent: Decimal = Decimal("15.00")
    inflation_volatility_percent: Decimal = Decimal("1.50")
    lookback_months: int = 12
    shared_ledger_id: Optional[int] = None
    shared_share_percent: Optional[Decimal] = None
    wealth_tax_threshold: Decimal = Decimal("1760000")
    wealth_tax_rate_percent: Decimal = Decimal("1.000")
    wealth_tax_step2_threshold: Optional[Decimal] = Decimal("20700000")
    wealth_tax_step2_rate_percent: Optional[Decimal] = Decimal("1.100")
    wealth_tax_index_threshold: bool = True
    excluded_account_ids: List[int] = []


class FireCostAccount(BaseModel):
    """An expense account an obligation may already be booked on.

    Carries its ledger because the one that matters most — the interest on a
    shared mortgage — lives in the household's ledger, not the owner's.
    """
    id: int
    ledger_id: int
    ledger_name: str
    account_number: str
    account_name: str


class FireIncomeStreamInput(BaseModel):
    """A pension paid as income from an age: folketrygd, tjenestepensjon."""
    id: Optional[int] = None
    name: str
    monthly_amount: Decimal = Decimal("0")
    start_age: int
    end_age: Optional[int] = None
    inflation_adjusted: bool = True
    is_active: bool = True


class FireIncomeStreamOut(FireIncomeStreamInput):
    id: int

    class Config:
        from_attributes = True


class FireSettingsOut(FireSettingsUpdate):
    ledger_id: int
    obligations: List[FireObligationOut] = []
    income_streams: List[FireIncomeStreamOut] = []
    updated_at: Optional[datetime] = None


class FireBucket(BaseModel):
    name: str
    amount: Decimal
    unlock_age: Optional[int] = None
    payout_years: Optional[int] = None
    annual_contribution: Decimal = Decimal("0")
    valuation_percent: Decimal
    excluded: bool


class FireYearRow(BaseModel):
    year: int
    age: int
    available: Decimal
    locked: Decimal
    excluded: Decimal
    total: Decimal
    debt: Decimal
    net_wealth: Decimal
    spending: Decimal
    obligations: Decimal
    wealth_tax: Decimal
    saved: Decimal
    withdrawn: Decimal
    working: bool
    pension_income: Decimal = Decimal("0")
    """Months the row covers; the first and last of a plan are part-years."""
    months: int = 12


class FireChartPoint(BaseModel):
    """One year on the chart. Capital on the left axis, the rest on the right."""
    year: int
    age: int
    """What the pots hold if the saving carries on as it does now."""
    capital_saving: Decimal
    """What they hold if nothing is ever added — only the return."""
    capital_no_deposits: Decimal
    """Spending plus the obligations still running plus the wealth tax."""
    annual_cost: Decimal
    """The same, less the pensions. What the capital itself has to raise."""
    annual_need: Decimal
    pension_income: Decimal


class FireChart(BaseModel):
    """The accumulation picture: two capital paths against what a year costs.

    The right-hand axis is the left-hand one times the withdrawal rate, so
    the capital curve read on the right *is* the four per cent line and the
    crossing with the cost curve is real rather than an artefact of scaling
    two axes independently.
    """
    swr_percent: Decimal
    points: List[FireChartPoint]
    """First year a four per cent withdrawal covers the year's need."""
    crossing_year: Optional[int] = None
    crossing_age: Optional[int] = None


class FireObligationOutcome(BaseModel):
    name: str
    kind: str
    monthly: Decimal
    ends: Optional[date] = None
    """True when the date was amortised out rather than entered."""
    derived: bool
    total_interest: Decimal
    frees_up_cash: bool


class FireProjectionOut(BaseModel):
    retirement_date: date
    retirement_age: int
    success: bool
    depleted_date: Optional[date] = None
    bridge_low: Optional[Decimal] = None
    bridge_low_date: Optional[date] = None
    first_wealth_tax_year: Optional[int] = None
    rows: List[FireYearRow]
    obligations: List[FireObligationOutcome]


class FireNumberOut(BaseModel):
    perpetual_annual_spending: Decimal
    base_capital: Decimal
    pension_capital: Decimal = Decimal("0")
    wealth_tax_annual: Decimal
    wealth_tax_capital: Decimal
    """Extra capital needed to carry the costs that do end, until they do."""
    bridge_capital: Decimal
    total: Decimal


class FireAssumptions(BaseModel):
    as_of: date
    birth_date: date
    age: int
    horizon_age: int
    monthly_spending: Decimal
    monthly_net_income: Decimal
    monthly_obligations: Decimal
    swr_percent: Decimal
    inflation_percent: Decimal
    expected_return_percent: Decimal
    real_return_percent: Decimal
    capital_available: Decimal
    capital_locked: Decimal
    capital_excluded: Decimal
    buckets: List[FireBucket]


class FireResult(BaseModel):
    ledger_id: int
    assumptions: FireAssumptions
    fire_number: FireNumberOut
    earliest: Optional[FireProjectionOut] = None
    target: Optional[FireProjectionOut] = None
    chart: Optional[FireChart] = None
    warnings: List[str] = []
