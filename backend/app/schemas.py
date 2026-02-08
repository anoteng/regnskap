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


class LedgerBase(BaseModel):
    name: str


class LedgerCreate(LedgerBase):
    pass


class Ledger(LedgerBase):
    id: int
    created_by: int
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
    parent_account_id: Optional[int] = None
    is_active: bool
    is_system: bool
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
    created_at: datetime
    journal_entries: List[JournalEntry] = []

    class Config:
        from_attributes = True


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
    account_number: str
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
    account_number: str
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


# Rebuild models to resolve forward references
JournalEntry.model_rebuild()
