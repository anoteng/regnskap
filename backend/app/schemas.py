from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class Token(BaseModel):
    access_token: str
    token_type: str


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


class LedgerCreate(LedgerBase):
    chart_template_id: Optional[int] = None


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
    description: Optional[str] = None


class Account(AccountBase):
    id: int
    ledger_id: int
    parent_account_id: Optional[int] = None
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
    debit: Decimal = Field(default=Decimal("0.00"), ge=0)
    credit: Decimal = Field(default=Decimal("0.00"), ge=0)
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


class PaginatedTransactions(BaseModel):
    transactions: List[Transaction]
    total: int
    skip: int
    limit: int


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
    receipt_date: Optional[date] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None


class ReceiptCreate(ReceiptBase):
    pass


class Receipt(ReceiptBase):
    id: int
    ledger_id: int
    uploaded_by: int
    image_path: str
    original_filename: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    status: str
    matched_transaction_id: Optional[int] = None
    matched_at: Optional[datetime] = None
    matched_by: Optional[int] = None
    ai_extracted_date: Optional[date] = None
    ai_extracted_amount: Optional[Decimal] = None
    ai_extracted_vendor: Optional[str] = None
    ai_extracted_description: Optional[str] = None
    ai_suggested_account: Optional[str] = None
    ai_confidence: Optional[Decimal] = None
    ai_processed_at: Optional[datetime] = None
    ai_processing_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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
    created_at: datetime
    created_by: int

    class Config:
        from_attributes = True


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
