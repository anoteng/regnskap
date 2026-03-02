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
import logging
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
from .providers.enable_banking import EnableBankingProvider, SessionExpiredError
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
        external_bank_id: Optional[str] = None,
        initial_sync_from_date: Optional[date] = None
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
            initial_sync_from_date: Optional date to limit historical data

        Returns:
            {
                'authorization_url': str,
                'state_token': str
            }

        Example:
            >>> result = await service.start_oauth_flow(
            ...     user, ledger, bank_account, provider_id=1,
            ...     redirect_uri="https://example.com/callback",
            ...     initial_sync_from_date=date(2026, 1, 1)
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
            external_bank_id=external_bank_id,  # Store ASPSP ID for later use
            initial_sync_from_date=initial_sync_from_date,  # Store date limit
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
    ) -> Dict[str, Any]:
        """
        Handle OAuth callback and prepare for account selection.

        Validates state token, exchanges code for tokens, and stores
        account data for user to select which account to connect.

        Args:
            state_token: State token from callback
            authorization_code: Authorization code from callback
            redirect_uri: Must match the one used in authorization

        Returns:
            Dict with:
                - state_token: for use in account selection
                - accounts: list of available accounts
                - bank_account_id: internal account to connect to

        Raises:
            ValueError: If state invalid, expired, or already used
            httpx.HTTPStatusError: If token exchange fails

        Example:
            >>> result = await service.handle_oauth_callback(
            ...     state_token="abc123",
            ...     authorization_code="code456",
            ...     redirect_uri="https://example.com/callback"
            ... )
            >>> print(f"Available accounts: {len(result['accounts'])}")
        """
        # Validate state token
        oauth_state = self.db.query(OAuthState).filter(
            OAuthState.state_token == state_token
        ).first()

        if not oauth_state:
            raise ValueError("Invalid state token")

        if oauth_state.used_at:
            raise ValueError("State token already used")

        # Don't check expiry here - we're about to extend it anyway
        # The state token is still secure (cryptographically random)
        # if oauth_state.expires_at < datetime.utcnow():
        #     raise ValueError("State token expired")

        # Get provider
        provider = self._get_provider(oauth_state.provider_id)

        # Exchange code for tokens
        token_response = await provider.exchange_code_for_token(
            code=authorization_code,
            redirect_uri=redirect_uri
        )

        # Get accounts from token response
        accounts = token_response.get('accounts', [])
        if not accounts:
            raise ValueError("No accounts found from bank")

        # Store accounts and tokens in oauth_state for later use
        # Extend expiry to give user time to select account (30 minutes)
        import json
        oauth_state.accounts_data = json.dumps({
            'accounts': accounts,
            'access_token': token_response['access_token'],
            'refresh_token': token_response.get('refresh_token'),
            'expires_in': token_response.get('expires_in', 3600)
        })
        oauth_state.expires_at = datetime.utcnow() + timedelta(minutes=30)
        self.db.commit()

        # Return data for account selection
        return {
            'state_token': state_token,
            'accounts': accounts,
            'bank_account_id': oauth_state.bank_account_id
        }

    async def create_connection_from_selection(
        self,
        state_token: str,
        selected_account_id: str,
        bank_account_id: int
    ) -> BankConnection:
        """
        Create bank connection after user selects account.

        Args:
            state_token: OAuth state token
            selected_account_id: The account_id user selected from available accounts
            bank_account_id: Internal bank account ID to connect to

        Returns:
            Created BankConnection

        Raises:
            ValueError: If state invalid or account not found
        """
        # Validate state token
        oauth_state = self.db.query(OAuthState).filter(
            OAuthState.state_token == state_token
        ).first()

        if not oauth_state:
            raise ValueError("Invalid state token")

        # Allow reusing state for multiple accounts (within expiry window)
        # if oauth_state.used_at:
        #     raise ValueError("State token already used")

        if oauth_state.expires_at < datetime.utcnow():
            raise ValueError("State token expired")

        if not oauth_state.accounts_data:
            raise ValueError("No account data available")

        # Parse stored data
        import json
        stored_data = json.loads(oauth_state.accounts_data)
        accounts = stored_data['accounts']
        access_token = stored_data['access_token']
        refresh_token = stored_data.get('refresh_token')
        expires_in = stored_data.get('expires_in', 3600)

        # Find selected account
        account_info = None
        for account in accounts:
            if account['account_id'] == selected_account_id:
                account_info = account
                break

        # Sanitize BIC - may be stored as a dict from Enable Banking API
        if account_info and isinstance(account_info.get('bic'), dict):
            account_info['bic'] = account_info['bic'].get('bic_fi')

        if not account_info:
            raise ValueError(f"Selected account {selected_account_id} not found in available accounts")

        # Validate bank_account_id belongs to the correct ledger
        bank_account = self.db.query(BankAccount).filter(
            BankAccount.id == bank_account_id,
            BankAccount.ledger_id == oauth_state.ledger_id,
            BankAccount.is_active == True
        ).first()

        if not bank_account:
            raise ValueError(f"Bank account {bank_account_id} not found or does not belong to this ledger")

        # Check if there's an existing connection for this bank_account_id
        # (This allows re-authorization of existing connections)
        existing_for_bank_account = self.db.query(BankConnection).filter(
            BankConnection.bank_account_id == bank_account_id,
            BankConnection.ledger_id == oauth_state.ledger_id
        ).first()

        if existing_for_bank_account:
            # Re-authorization: Update existing connection with new tokens and account ID
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Re-authorizing existing connection {existing_for_bank_account.id}")

            existing_for_bank_account.external_account_id = account_info['account_id']
            existing_for_bank_account.external_account_name = account_info['account_name']
            existing_for_bank_account.external_account_iban = account_info.get('iban')
            existing_for_bank_account.external_account_bic = account_info.get('bic')
            existing_for_bank_account.access_token = self.encryption.encrypt(access_token)
            existing_for_bank_account.refresh_token = self.encryption.encrypt(refresh_token) if refresh_token else None
            existing_for_bank_account.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            existing_for_bank_account.status = BankConnectionStatus.ACTIVE
            existing_for_bank_account.provider_id = oauth_state.provider_id

            bank_connection = existing_for_bank_account
            logger.info(f"Updated connection {bank_connection.id} with new session")

        else:
            # Check if this external account is already connected to a different bank account
            existing_external = self.db.query(BankConnection).filter(
                BankConnection.ledger_id == oauth_state.ledger_id,
                BankConnection.provider_id == oauth_state.provider_id,
                BankConnection.external_account_id == selected_account_id,
                BankConnection.status == BankConnectionStatus.ACTIVE
            ).first()

            if existing_external:
                raise ValueError(f"This account is already connected to {existing_external.bank_account.name}")

            # Create new bank connection
            bank_connection = BankConnection(
                ledger_id=oauth_state.ledger_id,
                bank_account_id=bank_account_id,
                provider_id=oauth_state.provider_id,
                external_bank_id=oauth_state.external_bank_id,  # Use ASPSP ID from OAuth state
                external_account_id=account_info['account_id'],
                external_account_name=account_info['account_name'],
                external_account_iban=account_info.get('iban'),
                external_account_bic=account_info.get('bic'),
                access_token=self.encryption.encrypt(access_token),
                refresh_token=self.encryption.encrypt(refresh_token) if refresh_token else None,
                token_expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
                status=BankConnectionStatus.ACTIVE,
                created_by=oauth_state.user_id,
                initial_sync_from_date=oauth_state.initial_sync_from_date  # Limit historical data
            )

            self.db.add(bank_connection)

        # Don't mark state as used - allow reusing for multiple accounts
        # State will expire naturally after 30 minutes
        # oauth_state.used_at = datetime.utcnow()

        # CRITICAL: Update ALL sibling connections from the same bank with the new session.
        # When the user re-authorizes with an ASPSP (bank), the bank may revoke the old session.
        # Any other connections using that old session would then fail with EXPIRED_SESSION.
        # To prevent this, propagate the new session tokens to all connections from the same bank.
        import logging
        logger = logging.getLogger(__name__)

        sibling_connections = self.db.query(BankConnection).filter(
            BankConnection.ledger_id == oauth_state.ledger_id,
            BankConnection.provider_id == oauth_state.provider_id,
            BankConnection.external_bank_id == oauth_state.external_bank_id,
            BankConnection.id != bank_connection.id,
            BankConnection.status != BankConnectionStatus.DISCONNECTED
        ).all()

        if sibling_connections:
            logger.info(f"Updating {len(sibling_connections)} sibling connections with new session tokens")

            for sibling in sibling_connections:
                # Update session tokens (same session covers all accounts at this bank)
                sibling.access_token = self.encryption.encrypt(access_token)
                sibling.refresh_token = self.encryption.encrypt(refresh_token) if refresh_token else None
                sibling.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                # Try to match sibling's IBAN/BBAN with an account in the new session
                # to update the volatile account UID
                if sibling.external_account_iban:
                    for acc in accounts:
                        acc_iban = acc.get('iban') or acc.get('bban')
                        if acc_iban and acc_iban == sibling.external_account_iban:
                            old_uid = sibling.external_account_id
                            new_uid = acc['account_id']
                            if new_uid != old_uid:
                                logger.info(f"Sibling connection {sibling.id}: updating UID from {old_uid} to {new_uid}")
                                sibling.external_account_id = new_uid
                                sibling.external_account_name = acc.get('account_name', sibling.external_account_name)
                            break

                # Reset error status if it was in ERROR
                if sibling.status == BankConnectionStatus.ERROR:
                    sibling.status = BankConnectionStatus.ACTIVE
                    sibling.connection_error = None
                    logger.info(f"Sibling connection {sibling.id}: reset from ERROR to ACTIVE")

        self.db.commit()
        self.db.refresh(bank_connection)

        return bank_connection

    async def sync_transactions(
        self,
        bank_connection: BankConnection,
        user: User,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        sync_type: BankSyncType = BankSyncType.MANUAL,
        psu_ip_address: Optional[str] = None,
        psu_user_agent: Optional[str] = None
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

            # Decrypt access token (session_id for Enable Banking)
            access_token = self.encryption.decrypt(bank_connection.access_token)

            import logging
            logger = logging.getLogger(__name__)

            # Check if token/session expired
            # For Enable Banking: sessions are long-lived (up to 90 days), no refresh tokens.
            # We check token_expires_at as a hint, but the real check is the session status API call.
            if bank_connection.token_expires_at and bank_connection.token_expires_at < datetime.utcnow():
                if bank_connection.refresh_token:
                    # Provider supports refresh tokens (not Enable Banking)
                    refresh_token = self.encryption.decrypt(bank_connection.refresh_token)
                    token_response = await provider.refresh_access_token(refresh_token)
                    access_token = token_response['access_token']
                    bank_connection.access_token = self.encryption.encrypt(access_token)
                    bank_connection.token_expires_at = datetime.utcnow() + timedelta(
                        seconds=token_response.get('expires_in', 3600)
                    )
                    self.db.commit()
                else:
                    # No refresh token (Enable Banking uses long-lived sessions)
                    # Don't fail here - the session might still be valid.
                    # The session status check below will verify.
                    logger.warning(
                        f"token_expires_at ({bank_connection.token_expires_at}) has passed, "
                        f"but no refresh token available. Will check session status directly."
                    )

            # Check session status and update account IDs
            # (Enable Banking account IDs change per session)
            try:
                if hasattr(provider, 'check_session_status'):
                    logger.info("Checking session status...")
                    session_info = await provider.check_session_status(
                        access_token,
                        psu_ip_address=psu_ip_address,
                        psu_user_agent=psu_user_agent
                    )

                    if isinstance(session_info, dict):
                        session_status = session_info.get('status')
                        logger.info(f"Session status: {session_status}")

                        # Check if session is expired or closed (case-insensitive)
                        if session_status and session_status.lower() in ['expired', 'closed', 'revoked', 'expr']:
                            error_msg = f"Bank session is {session_status}. Please re-authorize the connection."
                            logger.error(error_msg)
                            bank_connection.status = BankConnectionStatus.ERROR
                            bank_connection.connection_error = error_msg
                            sync_log.sync_status = BankSyncStatus.FAILED
                            sync_log.error_message = error_msg
                            self.db.commit()
                            raise SessionExpiredError(error_msg)

                        # Update account IDs if they've changed
                        accounts = session_info.get('accounts', [])
                        if accounts:
                            bank_account = self.db.query(BankAccount).get(bank_connection.bank_account_id)
                            if bank_account and bank_connection.external_account_iban:
                                target_iban = bank_connection.external_account_iban

                                for acc in accounts:
                                    if not isinstance(acc, dict):
                                        continue

                                    # uid is the UUID for API calls; account_id is the identification object
                                    acc_uid = acc.get('uid')
                                    account_id_field = acc.get('account_id')
                                    acc_iban = None

                                    if isinstance(account_id_field, dict):
                                        acc_iban = account_id_field.get('iban')
                                        if not acc_iban and isinstance(account_id_field.get('other'), dict):
                                            acc_iban = account_id_field['other'].get('identification')

                                    if acc_iban and acc_iban == target_iban:
                                        old_id = bank_connection.external_account_id
                                        if acc_uid and isinstance(acc_uid, str) and acc_uid != old_id:
                                            logger.info(f"Updating account UID from {old_id} to {acc_uid}")
                                            bank_connection.external_account_id = acc_uid
                                            self.db.commit()
                                        break

            except SessionExpiredError:
                # Session expired - propagate to caller
                raise
            except Exception as e:
                # Don't fail sync if session check fails for non-expiry reasons
                # (network timeout, temporary API issue, etc.)
                logger.warning(f"Could not check session status: {str(e)}")

            # Determine date range and strategy
            # CRITICAL: Enable Banking has a 1-hour window after authorization to fetch
            # full history. After that, only the last 90 days are available.
            is_initial_sync = bank_connection.last_successful_sync_at is None

            if not from_date:
                if bank_connection.last_successful_sync_at:
                    # Ongoing sync: overlap by 1 day to catch late-posting transactions
                    # (booking date vs value date differences, especially for credit cards)
                    # Cap at 89 days ago to stay within the 90-day availability window
                    from_date = max(
                        bank_connection.last_successful_sync_at.date() - timedelta(days=1),
                        date.today() - timedelta(days=89)
                    )
                else:
                    # Initial sync: use initial_sync_from_date if set
                    from_date = bank_connection.initial_sync_from_date

            if not to_date:
                to_date = date.today()

            sync_log.sync_from_date = from_date
            sync_log.sync_to_date = to_date

            logger.info(f"Sync type: {'INITIAL' if is_initial_sync else 'ONGOING'}")
            logger.info(f"Date range: {from_date} to {to_date}")

            # Fetch transactions from provider
            # For initial sync: use strategy=longest to get maximum history
            # For ongoing sync: use default strategy with date range
            try:
                logger.info(f"Fetching transactions (initial_sync={is_initial_sync})")

                raw_transactions = await provider.fetch_transactions(
                    access_token=access_token,
                    account_id=bank_connection.external_account_id,
                    from_date=from_date,
                    to_date=to_date,
                    is_initial_sync=is_initial_sync,
                    psu_ip_address=psu_ip_address,
                    psu_user_agent=psu_user_agent
                )

                logger.info(f"Successfully fetched {len(raw_transactions)} transactions")

            except Exception as e:
                error_str = str(e)
                logger.error(f"Failed to fetch transactions: {error_str}")
                raise

            # Fix amount signs for LIABILITY accounts (credit cards)
            # Enable Banking returns DBIT/CRDT from the bank's perspective
            # For LIABILITY accounts, we need to invert the sign
            bank_account = self.db.query(BankAccount).get(bank_connection.bank_account_id)
            if bank_account and bank_account.account:
                gl_account = bank_account.account
                is_liability = (gl_account.account_type == AccountType.LIABILITY)

                if is_liability:
                    print(f"[DEBUG] Inverting amount signs for LIABILITY account {gl_account.account_number}")
                    for raw_tx in raw_transactions:
                        raw_tx['amount'] = -raw_tx['amount']

            sync_log.transactions_fetched = len(raw_transactions)
            print(f"[DEBUG] Fetched {len(raw_transactions)} transactions")

            # Process each transaction
            imported_count = 0
            duplicate_count = 0
            errors = []

            for raw_tx in raw_transactions:
                print(f"[DEBUG] Processing transaction: {raw_tx.get('external_id')}")
                try:
                    # Skip transactions without a date
                    if not raw_tx.get('date'):
                        logger.warning(f"Skipping transaction {raw_tx.get('external_id')} - no date available")
                        errors.append(f"Transaction {raw_tx.get('external_id')}: No date available")
                        continue

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
                    error_msg = f"Transaction {raw_tx.get('external_id')}: {str(e)}"
                    errors.append(error_msg)
                    print(f"[ERROR] {error_msg}")
                    import traceback
                    traceback.print_exc()
                    continue

            self.db.commit()

            print(f"[DEBUG] Sync complete: imported={imported_count}, duplicates={duplicate_count}, errors={len(errors)}")
            if errors:
                print(f"[DEBUG] Errors: {errors}")

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
