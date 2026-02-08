"""
Bank Integration Service

Main orchestration service that handles:
- OAuth flow management
- Provider selection and initialization
- Transaction synchronization
- Deduplication
- Import as DRAFT transactions
"""

import secrets
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.app.models import (
    BankProvider, BankConnection, BankTransaction, BankSyncLog,
    OAuthState, User, Ledger, BankAccount, Transaction, JournalEntry,
    Account, AccountType, TransactionStatus, TransactionSource,
    BankConnectionStatus, BankSyncType, BankSyncStatus,
    BankTransactionImportStatus
)

from .providers.base import BaseBankProvider
from .providers.enable_banking import EnableBankingProvider
from .encryption import TokenEncryption
from .deduplication import TransactionDeduplicator


class BankIntegrationService:
    """
    Main service for bank integration.

    Provides high-level operations for:
    - Starting OAuth flows
    - Handling OAuth callbacks
    - Syncing transactions
    - Disconnecting banks
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.encryption = TokenEncryption()
        self._provider_cache = {}

    def _get_provider(self, provider_id: int) -> BaseBankProvider:
        """
        Get provider instance (cached).

        Args:
            provider_id: BankProvider ID

        Returns:
            Initialized provider instance

        Raises:
            ValueError: If provider not found or unsupported
        """
        # Check cache
        if provider_id in self._provider_cache:
            return self._provider_cache[provider_id]

        # Load provider config
        provider_config = self.db.query(BankProvider).get(provider_id)
        if not provider_config:
            raise ValueError(f"Provider {provider_id} not found")

        if not provider_config.is_active:
            raise ValueError(f"Provider {provider_config.name} is not active")

        # Create provider instance based on name
        if provider_config.name == 'enable_banking':
            provider = EnableBankingProvider(provider_config)
        elif provider_config.name == 'tink':
            # Future: TinkProvider(provider_config)
            raise ValueError("Tink provider not yet implemented")
        elif provider_config.name == 'neonomics':
            # Future: NeonomicsProvider(provider_config)
            raise ValueError("Neonomics provider not yet implemented")
        else:
            raise ValueError(f"Unsupported provider: {provider_config.name}")

        # Cache and return
        self._provider_cache[provider_id] = provider
        return provider

    async def start_oauth_flow(
        self,
        user: User,
        ledger: Ledger,
        bank_account: BankAccount,
        provider_id: int,
        redirect_uri: str,
        external_bank_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate OAuth flow for connecting a bank account.

        Creates an OAuth state token for CSRF protection and generates
        the authorization URL.

        Args:
            user: Current user
            ledger: Current ledger
            bank_account: Which bank account to connect
            provider_id: Which provider to use
            redirect_uri: Where to redirect after authorization
            external_bank_id: Optional bank/ASPSP selection

        Returns:
            {
                'authorization_url': str,
                'state_token': str
            }

        Example:
            >>> result = await service.start_oauth_flow(
            ...     user, ledger, bank_account, provider_id=1,
            ...     redirect_uri="https://example.com/callback"
            ... )
            >>> # Redirect user to result['authorization_url']
        """
        # Generate random state token (CSRF protection)
        state_token = secrets.token_urlsafe(32)

        # Create OAuth state record
        oauth_state = OAuthState(
            state_token=state_token,
            user_id=user.id,
            ledger_id=ledger.id,
            bank_account_id=bank_account.id,
            provider_id=provider_id,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        self.db.add(oauth_state)
        self.db.commit()

        # Get provider and generate authorization URL
        provider = self._get_provider(provider_id)
        authorization_url = await provider.get_authorization_url(
            state=state_token,
            redirect_uri=redirect_uri,
            bank_id=external_bank_id
        )

        return {
            'authorization_url': authorization_url,
            'state_token': state_token
        }

    async def handle_oauth_callback(
        self,
        state_token: str,
        authorization_code: str,
        redirect_uri: str
    ) -> BankConnection:
        """
        Handle OAuth callback and complete connection.

        Validates state token, exchanges code for tokens, and creates
        bank connection record.

        Args:
            state_token: State token from callback
            authorization_code: Authorization code from callback
            redirect_uri: Must match the one used in authorization

        Returns:
            Created BankConnection

        Raises:
            ValueError: If state invalid, expired, or already used
            httpx.HTTPStatusError: If token exchange fails

        Example:
            >>> connection = await service.handle_oauth_callback(
            ...     state_token="abc123",
            ...     authorization_code="code456",
            ...     redirect_uri="https://example.com/callback"
            ... )
            >>> print(f"Connected bank account: {connection.external_account_id}")
        """
        # Validate state token
        oauth_state = self.db.query(OAuthState).filter(
            OAuthState.state_token == state_token
        ).first()

        if not oauth_state:
            raise ValueError("Invalid state token")

        if oauth_state.used_at:
            raise ValueError("State token already used")

        if oauth_state.expires_at < datetime.utcnow():
            raise ValueError("State token expired")

        # Mark state as used
        oauth_state.used_at = datetime.utcnow()
        self.db.commit()

        # Get provider
        provider = self._get_provider(oauth_state.provider_id)

        # Exchange code for tokens
        token_response = await provider.exchange_code_for_token(
            code=authorization_code,
            redirect_uri=redirect_uri
        )

        # Extract tokens
        access_token = token_response['access_token']
        refresh_token = token_response.get('refresh_token')
        expires_in = token_response.get('expires_in', 3600)

        # Fetch account details to get external_account_id
        accounts = await provider.fetch_accounts(access_token)
        if not accounts:
            raise ValueError("No accounts found from bank")

        # Use first account (user selected bank, we get their accounts)
        # In a more advanced implementation, let user choose which account
        account_info = accounts[0]

        # Create bank connection
        bank_connection = BankConnection(
            ledger_id=oauth_state.ledger_id,
            bank_account_id=oauth_state.bank_account_id,
            provider_id=oauth_state.provider_id,
            external_bank_id=oauth_state.provider.name,  # Or from account_info
            external_account_id=account_info['account_id'],
            external_account_name=account_info['account_name'],
            external_account_iban=account_info.get('iban'),
            external_account_bic=account_info.get('bic'),
            access_token=self.encryption.encrypt(access_token),
            refresh_token=self.encryption.encrypt(refresh_token) if refresh_token else None,
            token_expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
            status=BankConnectionStatus.ACTIVE,
            created_by=oauth_state.user_id
        )

        self.db.add(bank_connection)
        self.db.commit()
        self.db.refresh(bank_connection)

        return bank_connection

    async def sync_transactions(
        self,
        bank_connection: BankConnection,
        user: User,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        sync_type: BankSyncType = BankSyncType.MANUAL
    ) -> Dict[str, Any]:
        """
        Sync transactions from bank.

        Main workflow:
        1. Validate connection and refresh token if needed
        2. Fetch transactions from provider
        3. Store in bank_transactions table
        4. Deduplicate against existing transactions
        5. Import new transactions as DRAFT
        6. Log sync operation

        Args:
            bank_connection: Bank connection to sync
            user: User triggering sync (None for auto-sync)
            from_date: Start date (default: last sync or 90 days ago)
            to_date: End date (default: today)
            sync_type: MANUAL, AUTO, or OAUTH_CONNECT

        Returns:
            {
                'status': 'success' or 'failed',
                'transactions_fetched': int,
                'imported': int,
                'duplicates': int,
                'errors': List[str]
            }

        Example:
            >>> result = await service.sync_transactions(
            ...     bank_connection, user
            ... )
            >>> print(f"Imported {result['imported']} new transactions")
        """
        started_at = datetime.utcnow()

        # Create sync log
        sync_log = BankSyncLog(
            bank_connection_id=bank_connection.id,
            sync_type=sync_type,
            sync_status=BankSyncStatus.FAILED,  # Assume failure, update on success
            started_at=started_at,
            triggered_by=user.id if user else None
        )
        self.db.add(sync_log)
        self.db.flush()

        try:
            # Get provider
            provider = self._get_provider(bank_connection.provider_id)

            # Decrypt access token
            access_token = self.encryption.decrypt(bank_connection.access_token)

            # Check if token expired and refresh if needed
            if bank_connection.token_expires_at and bank_connection.token_expires_at < datetime.utcnow():
                if not bank_connection.refresh_token:
                    raise ValueError("Access token expired and no refresh token available")

                # Refresh token
                refresh_token = self.encryption.decrypt(bank_connection.refresh_token)
                token_response = await provider.refresh_access_token(refresh_token)

                # Update stored tokens
                access_token = token_response['access_token']
                bank_connection.access_token = self.encryption.encrypt(access_token)
                bank_connection.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=token_response.get('expires_in', 3600)
                )
                self.db.commit()

            # Determine date range
            if not from_date:
                # Default: last successful sync or 90 days ago
                if bank_connection.last_successful_sync_at:
                    from_date = bank_connection.last_successful_sync_at.date()
                else:
                    from_date = date.today() - timedelta(days=90)

            if not to_date:
                to_date = date.today()

            sync_log.sync_from_date = from_date
            sync_log.sync_to_date = to_date

            # Fetch transactions from provider
            raw_transactions = await provider.fetch_transactions(
                access_token=access_token,
                account_id=bank_connection.external_account_id,
                from_date=from_date,
                to_date=to_date
            )

            sync_log.transactions_fetched = len(raw_transactions)

            # Process each transaction
            imported_count = 0
            duplicate_count = 0
            errors = []

            for raw_tx in raw_transactions:
                try:
                    # Generate deduplication hash
                    dedup_hash = TransactionDeduplicator.generate_hash(
                        transaction_date=raw_tx['date'],
                        amount=raw_tx['amount'],
                        description=raw_tx['description'],
                        reference=raw_tx['reference']
                    )

                    # Check if already fetched
                    existing_bank_tx = TransactionDeduplicator.check_duplicate_bank_transaction(
                        self.db,
                        bank_connection.id,
                        raw_tx['external_id'],
                        dedup_hash
                    )

                    if existing_bank_tx:
                        duplicate_count += 1
                        continue

                    # Store in bank_transactions
                    bank_tx = BankTransaction(
                        bank_connection_id=bank_connection.id,
                        external_transaction_id=raw_tx['external_id'],
                        transaction_date=raw_tx['date'],
                        booking_date=raw_tx.get('booking_date'),
                        value_date=raw_tx.get('value_date'),
                        amount=raw_tx['amount'],
                        currency=raw_tx['currency'],
                        description=raw_tx['description'],
                        reference=raw_tx['reference'],
                        merchant_name=raw_tx.get('merchant_name'),
                        dedup_hash=dedup_hash,
                        raw_data=raw_tx['raw_data'],
                        import_status=BankTransactionImportStatus.PENDING
                    )
                    self.db.add(bank_tx)
                    self.db.flush()

                    # Check if duplicate of existing transaction
                    existing_tx = TransactionDeduplicator.find_duplicate_transaction(
                        self.db,
                        bank_connection.ledger_id,
                        bank_connection.bank_account.account_id,
                        dedup_hash,
                        raw_tx['date'],
                        raw_tx['amount']
                    )

                    if existing_tx:
                        # Mark as duplicate
                        bank_tx.import_status = BankTransactionImportStatus.DUPLICATE
                        bank_tx.imported_transaction_id = existing_tx.id
                        duplicate_count += 1
                    else:
                        # Import as DRAFT transaction
                        imported_tx = self._import_as_draft_transaction(
                            bank_connection,
                            raw_tx
                        )

                        bank_tx.import_status = BankTransactionImportStatus.IMPORTED
                        bank_tx.imported_transaction_id = imported_tx.id
                        imported_count += 1

                except Exception as e:
                    errors.append(f"Transaction {raw_tx.get('external_id')}: {str(e)}")
                    continue

            self.db.commit()

            # Update connection status
            bank_connection.last_sync_at = datetime.utcnow()
            bank_connection.last_successful_sync_at = datetime.utcnow()
            bank_connection.status = BankConnectionStatus.ACTIVE
            bank_connection.connection_error = None

            # Complete sync log
            sync_log.sync_status = BankSyncStatus.SUCCESS
            sync_log.transactions_imported = imported_count
            sync_log.transactions_duplicate = duplicate_count
            sync_log.completed_at = datetime.utcnow()
            sync_log.duration_seconds = int((datetime.utcnow() - started_at).total_seconds())

            self.db.commit()

            return {
                'status': 'success',
                'transactions_fetched': len(raw_transactions),
                'imported': imported_count,
                'duplicates': duplicate_count,
                'errors': errors
            }

        except Exception as e:
            # Log error
            sync_log.sync_status = BankSyncStatus.FAILED
            sync_log.error_message = str(e)
            sync_log.completed_at = datetime.utcnow()
            sync_log.duration_seconds = int((datetime.utcnow() - started_at).total_seconds())

            bank_connection.last_sync_at = datetime.utcnow()
            bank_connection.status = BankConnectionStatus.ERROR
            bank_connection.connection_error = str(e)

            self.db.commit()

            return {
                'status': 'failed',
                'transactions_fetched': 0,
                'imported': 0,
                'duplicates': 0,
                'errors': [str(e)]
            }

    def _import_as_draft_transaction(
        self,
        bank_connection: BankConnection,
        raw_tx: Dict[str, Any]
    ) -> Transaction:
        """
        Import bank transaction as DRAFT.

        Creates transaction with ONE journal entry for the bank account.
        User must add offsetting entry in posting queue.

        Args:
            bank_connection: Bank connection
            raw_tx: Normalized transaction data

        Returns:
            Created Transaction

        Logic:
            - ASSET account (bank): positive = debit, negative = credit
            - LIABILITY account (credit card): positive = credit, negative = debit
        """
        # Get bank account's linked GL account
        bank_account = self.db.query(BankAccount).get(bank_connection.bank_account_id)
        gl_account = self.db.query(Account).get(bank_account.account_id)

        # Create transaction
        transaction = Transaction(
            ledger_id=bank_connection.ledger_id,
            transaction_date=raw_tx['date'],
            description=raw_tx['description'] or 'Bank transaction',
            reference=raw_tx['reference'],
            status=TransactionStatus.DRAFT,
            source=TransactionSource.BANK_SYNC,
            source_reference=raw_tx['external_id']
        )
        self.db.add(transaction)
        self.db.flush()

        # Determine debit/credit based on account type and amount sign
        is_liability = (gl_account.account_type == AccountType.LIABILITY)
        amount = raw_tx['amount']

        if is_liability:
            # Credit card: positive amount = expense (increases liability = credit)
            #              negative amount = payment (decreases liability = debit)
            if amount > 0:
                journal_entry = JournalEntry(
                    transaction_id=transaction.id,
                    account_id=bank_account.account_id,
                    debit=Decimal("0.00"),
                    credit=abs(amount),
                    description=raw_tx['description']
                )
            else:
                journal_entry = JournalEntry(
                    transaction_id=transaction.id,
                    account_id=bank_account.account_id,
                    debit=abs(amount),
                    credit=Decimal("0.00"),
                    description=raw_tx['description']
                )
        else:
            # Bank account: positive amount = deposit (increases asset = debit)
            #               negative amount = withdrawal (decreases asset = credit)
            if amount > 0:
                journal_entry = JournalEntry(
                    transaction_id=transaction.id,
                    account_id=bank_account.account_id,
                    debit=abs(amount),
                    credit=Decimal("0.00"),
                    description=raw_tx['description']
                )
            else:
                journal_entry = JournalEntry(
                    transaction_id=transaction.id,
                    account_id=bank_account.account_id,
                    debit=Decimal("0.00"),
                    credit=abs(amount),
                    description=raw_tx['description']
                )

        self.db.add(journal_entry)
        return transaction

    async def disconnect_bank(
        self,
        bank_connection: BankConnection,
        user: User
    ):
        """
        Disconnect bank account.

        Revokes tokens and marks connection as disconnected.

        Args:
            bank_connection: Connection to disconnect
            user: User disconnecting

        Example:
            >>> await service.disconnect_bank(bank_connection, user)
            >>> # Connection is now DISCONNECTED
        """
        try:
            # Get provider and revoke token
            provider = self._get_provider(bank_connection.provider_id)
            access_token = self.encryption.decrypt(bank_connection.access_token)
            await provider.revoke_token(access_token)
        except Exception as e:
            # Log but don't fail - connection will be marked disconnected anyway
            print(f"Token revocation failed: {e}")

        # Update connection status
        bank_connection.status = BankConnectionStatus.DISCONNECTED
        bank_connection.access_token = None
        bank_connection.refresh_token = None
        bank_connection.token_expires_at = None

        self.db.commit()
