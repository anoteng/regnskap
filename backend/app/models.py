from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, DECIMAL, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from backend.database import Base


class AccountType(str, enum.Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class BankAccountType(str, enum.Enum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"
    CREDIT_CARD = "CREDIT_CARD"


class LedgerRole(str, enum.Enum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class TransactionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    RECONCILED = "RECONCILED"


class ReceiptStatus(str, enum.Enum):
    PENDING = "PENDING"
    MATCHED = "MATCHED"
    ARCHIVED = "ARCHIVED"


class BankConnectionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class BankSyncType(str, enum.Enum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"
    OAUTH_CONNECT = "OAUTH_CONNECT"


class BankSyncStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class BankTransactionImportStatus(str, enum.Enum):
    PENDING = "PENDING"
    IMPORTED = "IMPORTED"
    DUPLICATE = "DUPLICATE"
    IGNORED = "IGNORED"


class TransactionSource(str, enum.Enum):
    MANUAL = "MANUAL"
    CSV_IMPORT = "CSV_IMPORT"
    BANK_SYNC = "BANK_SYNC"


class Ledger(Base):
    __tablename__ = "ledgers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    creator = relationship("User", foreign_keys=[created_by], back_populates="created_ledgers")
    members = relationship("LedgerMember", back_populates="ledger")
    bank_accounts = relationship("BankAccount", back_populates="ledger")
    transactions = relationship("Transaction", back_populates="ledger")
    categories = relationship("Category", back_populates="ledger")
    budgets = relationship("Budget", back_populates="ledger")


class LedgerMember(Base):
    __tablename__ = "ledger_members"

    ledger_id = Column(Integer, ForeignKey("ledgers.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    role = Column(SQLEnum(LedgerRole), nullable=False, default=LedgerRole.MEMBER)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    ledger = relationship("Ledger", back_populates="members")
    user = relationship("User", back_populates="ledger_memberships")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    ai_access_enabled = Column(Boolean, default=True)
    ai_access_blocked_reason = Column(Text, nullable=True)
    last_active_ledger_id = Column(Integer, ForeignKey("ledgers.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    created_ledgers = relationship("Ledger", foreign_keys="Ledger.created_by", back_populates="creator")
    ledger_memberships = relationship("LedgerMember", back_populates="user")
    last_active_ledger = relationship("Ledger", foreign_keys=[last_active_ledger_id])
    webauthn_credentials = relationship("WebAuthnCredential", back_populates="user", cascade="all, delete-orphan")


class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    credential_id = Column(String(1024), unique=True, nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, default=0)
    credential_name = Column(String(255))
    transports = Column(Text)
    aaguid = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="webauthn_credentials")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True))

    user = relationship("User")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String(10), unique=True, nullable=False)
    account_name = Column(String(255), nullable=False)
    account_type = Column(SQLEnum(AccountType), nullable=False)
    parent_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parent_account = relationship("Account", remote_side=[id], backref="sub_accounts")
    journal_entries = relationship("JournalEntry", back_populates="account")
    ledger_settings = relationship("LedgerAccountSettings", back_populates="account")


class LedgerAccountSettings(Base):
    __tablename__ = "ledger_account_settings"

    ledger_id = Column(Integer, ForeignKey("ledgers.id"), primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), primary_key=True)
    is_hidden = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    ledger = relationship("Ledger")
    account = relationship("Account", back_populates="ledger_settings")


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Legacy, kept for now
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    name = Column(String(255), nullable=False)
    account_type = Column(SQLEnum(BankAccountType), nullable=False)
    account_number = Column(String(50))
    balance = Column(DECIMAL(15, 2), default=0.00)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    ledger = relationship("Ledger", back_populates="bank_accounts")
    account = relationship("Account")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Legacy, kept for now
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Audit trail
    transaction_date = Column(Date, nullable=False)
    description = Column(String(500), nullable=False)
    reference = Column(String(100))
    is_reconciled = Column(Boolean, default=False)
    status = Column(SQLEnum(TransactionStatus), nullable=False, default=TransactionStatus.POSTED)
    source = Column(SQLEnum(TransactionSource), default=TransactionSource.MANUAL)
    source_reference = Column(String(255), nullable=True)
    ai_suggested = Column(Boolean, default=False)
    ai_suggestion_data = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    ledger = relationship("Ledger", back_populates="transactions")
    creator = relationship("User", foreign_keys=[created_by])
    journal_entries = relationship("JournalEntry", back_populates="transaction", cascade="all, delete-orphan")
    receipts = relationship("Receipt", back_populates="transaction", cascade="all, delete-orphan")
    categories = relationship("Category", secondary="transaction_categories", back_populates="transactions")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    debit = Column(DECIMAL(15, 2), default=0.00)
    credit = Column(DECIMAL(15, 2), default=0.00)
    description = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transaction = relationship("Transaction", back_populates="journal_entries")
    account = relationship("Account", back_populates="journal_entries")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Legacy, kept for now
    name = Column(String(100), nullable=False)
    color = Column(String(7))
    icon = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ledger = relationship("Ledger", back_populates="categories")
    transactions = relationship("Transaction", secondary="transaction_categories", back_populates="categories")


class TransactionCategory(Base):
    __tablename__ = "transaction_categories"

    transaction_id = Column(Integer, ForeignKey("transactions.id"), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), primary_key=True)


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    year = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    ledger = relationship("Ledger", back_populates="budgets")
    creator = relationship("User")
    lines = relationship("BudgetLine", back_populates="budget", cascade="all, delete-orphan")


class BudgetLine(Base):
    __tablename__ = "budget_lines"

    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=False)
    account_number = Column(String(10), ForeignKey("accounts.account_number"), nullable=False)
    period = Column(Integer, nullable=False)  # 1-12 for months
    amount = Column(DECIMAL(15, 2), nullable=False, default=0)

    budget = relationship("Budget", back_populates="lines")
    account = relationship("Account")


class CSVMapping(Base):
    __tablename__ = "csv_mappings"

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Legacy, kept for now
    name = Column(String(255), nullable=False)
    date_column = Column(String(100), nullable=False)
    description_column = Column(String(100), nullable=False)
    amount_column = Column(String(100), nullable=False)
    reference_column = Column(String(100))
    date_format = Column(String(50), default='YYYY-MM-DD')
    decimal_separator = Column(String(1), default='.')
    delimiter = Column(String(1), default=',')
    invert_amount = Column(Boolean, default=False)
    skip_rows = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ImportLog(Base):
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Audit trail - who did the import
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False)
    csv_mapping_id = Column(Integer, ForeignKey("csv_mappings.id"))
    file_name = Column(String(255), nullable=False)
    rows_imported = Column(Integer, default=0)
    rows_failed = Column(Integer, default=0)
    import_date = Column(DateTime(timezone=True), server_default=func.now())


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id"), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # File storage
    image_path = Column(String(500), nullable=False)
    original_filename = Column(String(255))
    file_size = Column(Integer)
    mime_type = Column(String(100))

    # Metadata
    receipt_date = Column(Date, nullable=True)
    amount = Column(DECIMAL(10, 2), nullable=True)
    description = Column(Text, nullable=True)

    # AI-extracted data
    ai_extracted_date = Column(Date, nullable=True)
    ai_extracted_amount = Column(DECIMAL(10, 2), nullable=True)
    ai_extracted_vendor = Column(String(255), nullable=True)
    ai_extracted_description = Column(Text, nullable=True)
    ai_suggested_account = Column(String(10), nullable=True)
    ai_confidence = Column(DECIMAL(3, 2), nullable=True)
    ai_processed_at = Column(DateTime(timezone=True), nullable=True)
    ai_processing_error = Column(Text, nullable=True)

    # Matching status
    status = Column(SQLEnum(ReceiptStatus), nullable=False, default=ReceiptStatus.PENDING)
    matched_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    matched_at = Column(DateTime(timezone=True), nullable=True)
    matched_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    ledger = relationship("Ledger")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    matcher = relationship("User", foreign_keys=[matched_by])
    transaction = relationship("Transaction", foreign_keys=[matched_transaction_id])


class SubscriptionTier(str, enum.Enum):
    FREE = "FREE"
    BASIC = "BASIC"
    AI = "AI"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    PENDING = "PENDING"


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    tier = Column(SQLEnum(SubscriptionTier), nullable=False, unique=True)
    description = Column(Text)
    price_monthly = Column(DECIMAL(10, 2), nullable=False, default=0)
    features = Column(Text)  # JSON string of features
    max_documents = Column(Integer, nullable=True)  # NULL = unlimited
    max_monthly_uploads = Column(Integer, nullable=True)  # NULL = unlimited
    ai_enabled = Column(Boolean, default=False)
    max_ai_operations_per_month = Column(Integer, nullable=True)  # NULL = unlimited
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    subscriptions = relationship("UserSubscription", back_populates="plan")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)

    # Subscription period
    status = Column(SQLEnum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # NULL = never expires
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # Pricing overrides
    discount_percentage = Column(DECIMAL(5, 2), default=0)  # 0-100
    custom_price = Column(DECIMAL(10, 2), nullable=True)  # Override price if set
    is_free_forever = Column(Boolean, default=False)  # Free access permanently

    # Notes
    admin_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")


class UserMonthlyUsage(Base):
    __tablename__ = "user_monthly_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    upload_count = Column(Integer, default=0)
    ai_operations_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User")


class AIConfig(Base):
    __tablename__ = "ai_config"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False)  # openai, anthropic
    api_key = Column(Text, nullable=False)
    model = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    max_tokens = Column(Integer, default=4000)
    temperature = Column(DECIMAL(3, 2), default=0.3)
    config_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AIUsage(Base):
    __tablename__ = "ai_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ledger_id = Column(Integer, ForeignKey("ledgers.id"), nullable=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    operation_type = Column(String(50), nullable=False)
    tokens_used = Column(Integer, nullable=False)
    cost_usd = Column(DECIMAL(10, 6), nullable=True)
    request_data = Column(Text, nullable=True)
    response_data = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User")
    ledger = relationship("Ledger")


# Bank Integration Models

class BankProvider(Base):
    __tablename__ = "bank_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    environment = Column(String(20), nullable=False)
    config_data = Column(Text, nullable=True)
    authorization_url = Column(String(500), nullable=True)
    token_url = Column(String(500), nullable=True)
    api_base_url = Column(String(500), nullable=True)
    config_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    connections = relationship("BankConnection", back_populates="provider")


class BankConnection(Base):
    __tablename__ = "bank_connections"

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("ledgers.id"), nullable=False)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("bank_providers.id"), nullable=False)

    # External identifiers
    external_bank_id = Column(String(255), nullable=True)
    external_account_id = Column(String(255), nullable=False)
    external_account_name = Column(String(255), nullable=True)
    external_account_iban = Column(String(50), nullable=True)
    external_account_bic = Column(String(20), nullable=True)

    # OAuth tokens (encrypted)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Connection status
    status = Column(SQLEnum(BankConnectionStatus), default=BankConnectionStatus.ACTIVE)
    connection_error = Column(Text, nullable=True)

    # Sync settings
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_successful_sync_at = Column(DateTime(timezone=True), nullable=True)
    auto_sync_enabled = Column(Boolean, default=True)
    sync_frequency_hours = Column(Integer, default=24)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    ledger = relationship("Ledger")
    bank_account = relationship("BankAccount")
    provider = relationship("BankProvider", back_populates="connections")
    creator = relationship("User")
    transactions = relationship("BankTransaction", back_populates="connection")
    sync_logs = relationship("BankSyncLog", back_populates="connection")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, index=True)
    bank_connection_id = Column(Integer, ForeignKey("bank_connections.id"), nullable=False)

    # External identifiers
    external_transaction_id = Column(String(255), nullable=False)

    # Transaction data
    transaction_date = Column(Date, nullable=False)
    booking_date = Column(Date, nullable=True)
    value_date = Column(Date, nullable=True)
    amount = Column(DECIMAL(15, 2), nullable=False)
    currency = Column(String(3), default="NOK")
    description = Column(Text, nullable=True)
    reference = Column(String(255), nullable=True)

    # Merchant information
    merchant_name = Column(String(255), nullable=True)
    merchant_category = Column(String(100), nullable=True)

    # Deduplication
    dedup_hash = Column(String(32), nullable=False)

    # Import status
    import_status = Column(SQLEnum(BankTransactionImportStatus), default=BankTransactionImportStatus.PENDING)
    imported_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)

    # Raw data
    raw_data = Column(Text, nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    connection = relationship("BankConnection", back_populates="transactions")
    imported_transaction = relationship("Transaction")


class BankSyncLog(Base):
    __tablename__ = "bank_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    bank_connection_id = Column(Integer, ForeignKey("bank_connections.id"), nullable=False)

    # Sync operation
    sync_type = Column(SQLEnum(BankSyncType), nullable=False)
    sync_status = Column(SQLEnum(BankSyncStatus), nullable=False)

    # Results
    transactions_fetched = Column(Integer, default=0)
    transactions_imported = Column(Integer, default=0)
    transactions_duplicate = Column(Integer, default=0)

    # Date range
    sync_from_date = Column(Date, nullable=True)
    sync_to_date = Column(Date, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Who triggered
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    connection = relationship("BankConnection", back_populates="sync_logs")
    trigger_user = relationship("User")


class OAuthState(Base):
    __tablename__ = "oauth_states"

    id = Column(Integer, primary_key=True, index=True)
    state_token = Column(String(64), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ledger_id = Column(Integer, ForeignKey("ledgers.id"), nullable=False)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("bank_providers.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    ledger = relationship("Ledger")
    bank_account = relationship("BankAccount")
    provider = relationship("BankProvider")
