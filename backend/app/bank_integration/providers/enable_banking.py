"""
Enable Banking Provider Implementation

Enable Banking is a PSD2-compliant API that provides access to European banks.
Requires mTLS (mutual TLS) authentication with client certificates.

Documentation: https://enablebanking.com/docs/api/reference/
"""

import httpx
import json
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
from urllib.parse import urlencode
import jwt

from .base import BaseBankProvider


class SessionExpiredError(Exception):
    """Raised when an Enable Banking session has expired and re-authorization is needed."""
    pass


class EnableBankingProvider(BaseBankProvider):
    """
    Enable Banking API integration.

    Special requirements:
    - mTLS authentication (requires client certificate and private key)
    - ASPSP parameter for bank selection
    - Specific transaction format normalization
    """

    def __init__(self, provider_config):
        """
        Initialize Enable Banking provider.

        Extracts configuration:
        - api_key: Bearer token for authentication
        - app_id: Application ID from Enable Banking
        - certificate_path: Path to client certificate (.crt)
        - private_key_path: Path to private key (.key)
        """
        super().__init__(provider_config)

        # Extract configuration
        self.api_key = self.get_config_value('api_key')
        self.app_id = self.get_config_value('app_id')
        self.cert_path = self.get_config_value('certificate_path')
        self.private_key_path = self.get_config_value('private_key_path')

        # mTLS certificate tuple for httpx
        if self.cert_path and self.private_key_path:
            self.client_cert = (self.cert_path, self.private_key_path)
        else:
            self.client_cert = None

    def _generate_jwt_token(self) -> str:
        """
        Generate JWT token signed with private RSA key for Enable Banking API authentication.

        Returns:
            JWT token string
        """
        # Read private key
        with open(self.private_key_path, 'r') as f:
            private_key = f.read()

        # JWT header
        headers = {
            'typ': 'JWT',
            'alg': 'RS256',
            'kid': self.app_id  # Application ID as key ID
        }

        # JWT payload with clock skew tolerance
        now = datetime.now(UTC)  # Timezone-aware UTC time
        # Set iat 60 seconds in the past to account for clock skew
        iat_time = now - timedelta(seconds=60)
        # Set expiry 1 hour from now
        exp_time = now + timedelta(hours=1)

        payload = {
            'iss': 'enablebanking.com',
            'aud': 'api.enablebanking.com',
            'iat': int(iat_time.timestamp()),
            'exp': int(exp_time.timestamp())
        }

        # Sign and encode JWT
        token = jwt.encode(payload, private_key, algorithm='RS256', headers=headers)
        return token

    async def list_aspsps(self, country: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available ASPSPs (banks) from Enable Banking.

        Args:
            country: Optional ISO country code filter (e.g., 'NO', 'SE')

        Returns:
            List of ASPSP dicts with name, country, logo, psu_types
        """
        jwt_token = self._generate_jwt_token()

        params = {}
        if country:
            params['country'] = country

        async with httpx.AsyncClient(
            timeout=30.0,
            cert=self.client_cert
        ) as client:
            response = await client.get(
                f"{self.config.api_base_url}/aspsps",
                params=params,
                headers={
                    'Authorization': f'Bearer {jwt_token}',
                    'Accept': 'application/json'
                }
            )

            if response.status_code != 200:
                raise Exception(f"Failed to list ASPSPs: {response.text}")

            data = response.json()
            return data.get('aspsps', [])

    async def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        bank_id: Optional[str] = None
    ) -> str:
        """
        Initiate Enable Banking OAuth flow by POSTing to /auth endpoint.

        Enable Banking uses a non-standard OAuth flow:
        1. POST to /auth with JWT authentication
        2. Receive a redirect URL
        3. Redirect user to that URL

        Args:
            state: CSRF protection token
            redirect_uri: Callback URL
            bank_id: ASPSP identifier (e.g., 'NO_NORWEGIAN' for Bank Norwegian)

        Returns:
            URL to redirect user to (from Enable Banking response)
        """
        # Generate JWT for authentication
        jwt_token = self._generate_jwt_token()

        # Build request body according to Enable Banking spec
        request_body = {
            "access": {
                "valid_until": (datetime.now(UTC) + timedelta(days=90)).isoformat()
            },
            "state": state,
            "redirect_url": redirect_uri,
            "psu_type": "personal"
        }

        # Add ASPSP (bank) if specified
        # If not specified, Enable Banking will show bank selection screen
        if bank_id:
            # Parse bank_id into country and name
            # Format: "NO_Bank Name" -> country: "NO", name: "Bank Name"
            # The name must match exactly what Enable Banking returns from /aspsps
            if '_' in bank_id:
                parts = bank_id.split('_', 1)
                country = parts[0]
                bank_name = parts[1]
            else:
                country = "NO"
                bank_name = bank_id

            request_body["aspsp"] = {
                "name": bank_name,
                "country": country
            }

        # Make POST request to /auth
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Starting OAuth flow to {self.config.authorization_url}")
        logger.info(f"Request body: {request_body}")

        async with httpx.AsyncClient(
            timeout=30.0,
            cert=self.client_cert  # mTLS certificate
        ) as client:
            response = await client.post(
                self.config.authorization_url,
                json=request_body,
                headers={
                    'Authorization': f'Bearer {jwt_token}',
                    'Content-Type': 'application/json'
                }
            )

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response body: {response.text}")

            if response.status_code != 200:
                error_detail = response.json() if response.text else {"message": "Unknown error"}
                logger.error(f"Enable Banking error detail: {error_detail}")
                raise Exception(f"Enable Banking auth failed: {error_detail.get('message', response.text)}")

            result = response.json()
            # Return the URL that user should be redirected to
            return result['url']

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for session ID.

        Enable Banking uses session-based authentication (not standard OAuth tokens).
        POST /sessions returns a session_id that's used for subsequent API calls.

        Args:
            code: Authorization code from callback
            redirect_uri: Not used by Enable Banking (kept for interface compatibility)

        Returns:
            {
                'access_token': str (actually session_id),
                'expires_in': int (calculated from valid_until),
                'token_type': 'Bearer',
                'accounts': List[Dict] (account details from response)
            }

        Raises:
            httpx.HTTPStatusError: If session creation fails
        """
        # Generate JWT for authentication
        jwt_token = self._generate_jwt_token()

        async with httpx.AsyncClient(
            timeout=60.0,
            cert=self.client_cert  # mTLS
        ) as client:
            response = await client.post(
                self.config.token_url,  # https://api.enablebanking.com/sessions
                json={'code': code},  # JSON body, not form data
                headers={
                    'Authorization': f'Bearer {jwt_token}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            )

            response.raise_for_status()
            data = response.json()

            import logging
            logger = logging.getLogger(__name__)

            # Debug: Check if data is actually a dict
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict from API, got {type(data).__name__}: {data}")

            # Extract session_id and accounts
            session_id = data.get('session_id')
            if not session_id:
                raise ValueError(f"No session_id in response: {data}")

            # Log the full session response for debugging
            access_info = data.get('access', {})
            valid_until = access_info.get('valid_until') if isinstance(access_info, dict) else None
            logger.info(f"Session created: session_id={session_id[:8]}..., valid_until={valid_until}")
            logger.info(f"Full access info from bank: {access_info}")

            # Calculate expires_in from valid_until
            # Default to 90 days if parsing fails (Enable Banking sessions are long-lived)
            expires_in = 90 * 24 * 3600  # 90 days default
            if valid_until:
                try:
                    valid_until_dt = datetime.fromisoformat(valid_until.replace('Z', '+00:00'))
                    now = datetime.now(UTC)
                    expires_in = int((valid_until_dt - now).total_seconds())
                    logger.info(f"Session valid for {expires_in} seconds ({expires_in // 86400} days)")
                except Exception as e:
                    logger.warning(f"Could not parse valid_until '{valid_until}': {e}, using 90-day default")
            else:
                logger.warning("No valid_until in session response, using 90-day default")

            # Normalize accounts to internal format
            normalized_accounts = self._normalize_accounts(data)

            # Return in OAuth-like format for compatibility with service layer
            return {
                'access_token': session_id,
                'refresh_token': None,  # Enable Banking doesn't use refresh tokens
                'expires_in': expires_in,
                'token_type': 'Bearer',
                'accounts': normalized_accounts  # Include normalized accounts
            }

    async def refresh_access_token(
        self,
        refresh_token: str
    ) -> Dict[str, Any]:
        """
        Refresh an expired session.

        Enable Banking does NOT support session refresh. Sessions are valid
        until the 'valid_until' timestamp set during authorization (up to 90 days).

        When a session expires, users must re-authorize through the full OAuth flow.

        Args:
            refresh_token: Not used (Enable Banking doesn't issue refresh tokens)

        Returns:
            Never returns - always raises exception

        Raises:
            NotImplementedError: Enable Banking doesn't support token refresh
        """
        raise NotImplementedError(
            "Enable Banking does not support session refresh. "
            "Users must re-authorize when the session expires. "
            "Session validity is set during initial authorization (up to 90 days)."
        )

    async def fetch_accounts(
        self,
        access_token: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch list of accounts from the session.

        Enable Banking returns accounts during session creation (POST /sessions).
        This method fetches updated account info using GET /sessions/{session_id}.

        Args:
            access_token: session_id from Enable Banking

        Returns:
            List of accounts with normalized structure
        """
        # Generate JWT for authentication
        jwt_token = self._generate_jwt_token()

        async with httpx.AsyncClient(
            timeout=60.0,
            cert=self.client_cert
        ) as client:
            # Fetch session details to get current account list
            response = await client.get(
                f"{self.config.api_base_url}/sessions/{access_token}",
                headers={
                    'Authorization': f'Bearer {jwt_token}',
                    'Accept': 'application/json'
                }
            )

            response.raise_for_status()
            data = response.json()

            # GET /sessions returns different format than POST /sessions
            # accounts is a list of UIDs, accounts_data has minimal info
            # For now, we'll need to make individual account calls if full details needed
            # But typically we use accounts from POST /sessions response instead
            return self._normalize_accounts(data)

    async def check_session_status(
        self,
        session_id: str,
        psu_ip_address: Optional[str] = None,
        psu_user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if a session is still valid and get its current status.

        Returns session info including status and accounts.

        Raises:
            SessionExpiredError: If the session has expired (401 from API)
        """
        import logging
        logger = logging.getLogger(__name__)

        # Generate JWT for authentication
        jwt_token = self._generate_jwt_token()

        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/json'
        }
        if psu_ip_address:
            headers['PSU-IP-Address'] = psu_ip_address
        if psu_user_agent:
            headers['PSU-User-Agent'] = psu_user_agent

        async with httpx.AsyncClient(
            timeout=60.0,
            cert=self.client_cert
        ) as client:
            # Get session status from Enable Banking
            response = await client.get(
                f"{self.config.api_base_url}/sessions/{session_id}",
                headers=headers
            )

            if not response.is_success:
                error_body = response.text
                logger.error(f"Session status check failed - Status: {response.status_code}, Body: {error_body}")

                # Check for expired session specifically
                try:
                    error_data = response.json()
                    error_code = error_data.get('error', '')
                except:
                    error_code = ''

                if response.status_code == 401 or error_code == 'EXPIRED_SESSION':
                    raise SessionExpiredError(f"Bank session has expired. Please re-authorize. (Response: {error_body})")

                response.raise_for_status()

            session_data = response.json()

            if isinstance(session_data, dict):
                access = session_data.get('access', {})
                if isinstance(access, dict):
                    valid_until = access.get('valid_until')
                    logger.info(f"Session valid_until: {valid_until}")
                status = session_data.get('status')
                logger.info(f"Session status: {status}")
            else:
                logger.warning(f"Session data is not a dict: {session_data}")

            return session_data

    async def get_session_accounts(
        self,
        access_token: str
    ) -> List[Dict[str, Any]]:
        """
        Get current list of accounts from the session.
        This is useful for updating account IDs when they change.

        Note: access_token for Enable Banking is actually the session_id
        """
        import logging
        logger = logging.getLogger(__name__)

        # Generate JWT for authentication
        jwt_token = self._generate_jwt_token()

        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/json'
        }

        # Determine cert paths
        cert_path = self.config_data.get('certificate_path', '')
        private_key_path = self.config_data.get('private_key_path', '')

        if not cert_path or not private_key_path:
            raise ValueError("Certificate and private key paths must be configured")

        api_base_url = self.config.api_base_url

        try:
            async with httpx.AsyncClient(
                timeout=60.0,
                cert=(cert_path, private_key_path)
            ) as client:
                # Get session info which includes accounts
                # access_token is actually the session_id for Enable Banking
                response = await client.get(
                    f"{api_base_url}/sessions/{access_token}",
                    headers=headers
                )

                if not response.is_success:
                    logger.error(f"Enable Banking API error - Status: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                    response.raise_for_status()

                data = response.json()
                accounts = data.get('accounts', [])

                logger.info(f"Retrieved {len(accounts)} accounts from session")

                # Return list of accounts with their IDs and IBANs
                return [{
                    'account_id': acc.get('account_id'),
                    'iban': acc.get('account_id', {}).get('iban'),
                    'name': acc.get('name'),
                    'currency': acc.get('currency'),
                    'status': data.get('status')  # Include session status
                } for acc in accounts]

        except Exception as e:
            logger.error(f"Failed to get session accounts: {str(e)}")
            raise

    async def fetch_transactions(
        self,
        access_token: str,
        account_id: str,
        from_date: Optional[date],
        to_date: date,
        is_initial_sync: bool = False,
        psu_ip_address: Optional[str] = None,
        psu_user_agent: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch transactions for an account with pagination support.

        Enable Banking has important time-based access limitations:
        - Within ~1 hour after authorization: Can fetch full history (years)
        - After ~1 hour: Can only fetch last 90 days

        Strategy parameter:
        - 'longest': For initial sync - fetches maximum available history
        - 'default' (omitted): For ongoing syncs - requires valid date range

        Args:
            access_token: session_id from Enable Banking (not used in API call)
            account_id: Account UID from Enable Banking (from session response)
            from_date: Start date (YYYY-MM-DD) - None for initial sync with strategy=longest
            to_date: End date (YYYY-MM-DD)
            is_initial_sync: If True, uses strategy=longest to get maximum history

        Returns:
            List of normalized transactions (all pages combined)

        Example:
            >>> # Initial sync - get maximum history
            >>> transactions = await provider.fetch_transactions(
            ...     access_token="session_id",
            ...     account_id="account-uid-123",
            ...     from_date=None,
            ...     to_date=date.today(),
            ...     is_initial_sync=True
            ... )
            >>>
            >>> # Ongoing sync - last 30 days
            >>> transactions = await provider.fetch_transactions(
            ...     access_token="session_id",
            ...     account_id="account-uid-123",
            ...     from_date=date.today() - timedelta(days=30),
            ...     to_date=date.today(),
            ...     is_initial_sync=False
            ... )
        """
        import logging
        logger = logging.getLogger(__name__)

        # Generate JWT for authentication
        jwt_token = self._generate_jwt_token()

        # Build query parameters
        # IMPORTANT: Only use date_from, NOT date_to.
        # This matches the official Enable Banking Python example.
        # Some ASPSPs (e.g. Bank Norwegian) return 400 when date_to is included.
        params = {}

        if from_date:
            params['date_from'] = from_date.isoformat()
            logger.info(f"Fetching transactions from {from_date} (to_date omitted per API spec)")
        else:
            # No date specified - fetch last 90 days
            from datetime import timedelta
            default_from = (to_date - timedelta(days=90)).isoformat()
            params['date_from'] = default_from
            logger.info(f"No from_date specified, using default: {default_from}")

        # Fetch all pages using continuation_key
        all_transactions = []
        continuation_key = None
        page_num = 0

        async with httpx.AsyncClient(
            timeout=60.0,
            cert=self.client_cert
        ) as client:
            while True:
                page_num += 1

                # Add continuation_key to params if we have one
                current_params = params.copy()
                if continuation_key:
                    current_params['continuation_key'] = continuation_key
                    logger.info(f"Fetching page {page_num} with continuation_key")
                else:
                    logger.info(f"Fetching page {page_num} (initial request)")

                # Build headers - include PSU headers required by some ASPSPs (e.g. Bank Norwegian)
                request_headers = {
                    'Authorization': f'Bearer {jwt_token}',
                    'Accept': 'application/json'
                }
                if psu_ip_address:
                    request_headers['PSU-IP-Address'] = psu_ip_address
                if psu_user_agent:
                    request_headers['PSU-User-Agent'] = psu_user_agent

                response = await client.get(
                    f"{self.config.api_base_url}/accounts/{account_id}/transactions",
                    params=current_params,
                    headers=request_headers
                )

                # Handle errors with detailed information
                if not response.is_success:
                    error_body = response.text
                    logger.error(f"Enable Banking API error - Status: {response.status_code}")
                    logger.error(f"Response body: {error_body}")
                    logger.error(f"Request params: {current_params}")
                    logger.error(f"Request URL: {response.url}")

                    # Parse error code and raise descriptive exception
                    error_code = ''
                    try:
                        error_data = response.json()
                        error_code = error_data.get('error', '')
                    except:
                        pass

                    if error_code == 'EXPIRED_SESSION':
                        raise Exception(f"Bank session has expired. Please re-authorize the connection. (Response: {error_body})")
                    elif error_code == 'ASPSP_ERROR':
                        raise Exception(f"Bank returned an error (ASPSP_ERROR). This may require re-authorization. (Response: {error_body})")
                    else:
                        raise Exception(f"Enable Banking error {response.status_code}: {error_body}")
                data = response.json()

                # Normalize Enable Banking transaction format
                page_transactions = self._normalize_transactions(data)
                all_transactions.extend(page_transactions)

                logger.info(f"Page {page_num}: Fetched {len(page_transactions)} transactions "
                          f"(total so far: {len(all_transactions)})")

                # Check for continuation_key
                continuation_key = data.get('continuation_key')
                if not continuation_key:
                    logger.info("No continuation_key - all transactions fetched")
                    break

                # Safety limit to prevent infinite loops
                if page_num >= 100:
                    logger.warning(f"Reached page limit of 100, stopping pagination")
                    break

        logger.info(f"=== Transaction Fetch Complete ===")
        logger.info(f"Account ID: {account_id}")
        logger.info(f"Total pages: {page_num}")
        logger.info(f"Total transactions: {len(all_transactions)}")

        return all_transactions

    async def revoke_token(
        self,
        access_token: str
    ) -> bool:
        """
        Revoke access token (disconnect).

        Note: Enable Banking may not support explicit token revocation.
        The token will expire naturally based on expires_in.

        Args:
            access_token: Token to revoke

        Returns:
            True if revocation successful or not needed
        """
        # Enable Banking doesn't have explicit revoke endpoint in docs
        # Token will expire naturally
        # For proper disconnection, user should revoke consent in their bank
        return True

    def _normalize_accounts(self, api_response: Dict) -> List[Dict[str, Any]]:
        """
        Convert Enable Banking account format to internal format.

        Enable Banking format (actual):
        {
            "accounts": [
                {
                    "uid": "92d3bfe0-5659-4e12-985c-c2c285c4ae63",
                    "name": "Andreas Noteng",
                    "details": "Felleskonto",
                    "product": "SavingsAccount",
                    "currency": "NOK",
                    "account_id": {
                        "iban": null,
                        "other": {
                            "identification": "93551582505",
                            "scheme_name": "BBAN"
                        }
                    }
                }
            ]
        }

        Args:
            api_response: Raw response from Enable Banking (session or GET /sessions)

        Returns:
            Normalized account list
        """
        accounts = []

        for account in api_response.get('accounts', []):
            # Extract IBAN or BBAN identification
            account_id_obj = account.get('account_id', {})
            iban = account_id_obj.get('iban')
            bban = None

            if not iban and isinstance(account_id_obj.get('other'), dict):
                bban = account_id_obj['other'].get('identification')

            # Build account name from details or product
            details = account.get('details', '')
            product = account.get('product', 'Unknown')
            account_name = f"{details} ({product})" if details else product

            accounts.append({
                'account_id': account.get('uid'),  # UUID for API calls
                'account_name': account_name,
                'iban': iban or bban,  # Use BBAN if IBAN is not available (Norwegian accounts)
                'bban': bban,  # Bank account number for Norwegian accounts
                'bic': account.get('account_servicer', {}).get('bic_fi') if isinstance(account.get('account_servicer'), dict) else account.get('account_servicer'),  # BIC/SWIFT if available
                'currency': account.get('currency', 'NOK'),
                'account_type': product
            })

        return accounts

    def _normalize_transactions(self, api_response: Dict) -> List[Dict[str, Any]]:
        """
        Convert Enable Banking transaction format to internal format.

        Enable Banking format:
        {
            "transactions": {
                "booked": [
                    {
                        "transactionId": "tx-123",
                        "bookingDate": "2024-01-15",
                        "valueDate": "2024-01-15",
                        "transactionAmount": {
                            "amount": "-123.45",
                            "currency": "NOK"
                        },
                        "remittanceInformationUnstructured": "COFFEE SHOP",
                        "creditorName": "Coffee Shop AS",
                        "debtorName": null,
                        "endToEndId": "REF123"
                    }
                ],
                "pending": [...]
            }
        }

        Args:
            api_response: Raw response from Enable Banking

        Returns:
            Normalized transaction list for internal processing
        """
        import logging
        logger = logging.getLogger(__name__)

        transactions = []

        # Handle both dict and list responses
        if isinstance(api_response, list):
            # If response is directly a list of transactions
            logger.info(f"API response is a list with {len(api_response)} items")
            booked = api_response
        else:
            # Enable Banking format: { "transactions": [...], "continuation_key": null }
            transactions_obj = api_response.get('transactions', {})
            logger.info(f"transactions_obj type: {type(transactions_obj)}")

            if isinstance(transactions_obj, dict):
                # Older format: nested under 'booked'
                booked = transactions_obj.get('booked', [])
                logger.info(f"Found {len(booked)} booked transactions (nested dict format)")
            else:
                # Current format: transactions is directly a list
                booked = transactions_obj if isinstance(transactions_obj, list) else []
                logger.info(f"Found {len(booked)} transactions (direct list format)")

        for i, tx in enumerate(booked):
            logger.info(f"Processing transaction #{i+1}: {tx.get('entry_reference') or tx.get('transaction_id')}")
            logger.debug(f"Raw transaction data: {tx}")

            # Parse amount
            tx_amount = tx.get('transaction_amount', {})
            amount_str = tx_amount.get('amount', '0')
            amount = Decimal(str(amount_str))

            # Credit/Debit indicator determines sign
            # DBIT = debit (money out, negative), CRDT = credit (money in, positive)
            if tx.get('credit_debit_indicator') == 'DBIT':
                amount = -abs(amount)
            else:
                amount = abs(amount)

            # Get merchant name from creditor or debtor
            creditor = tx.get('creditor')
            debtor = tx.get('debtor')
            if isinstance(creditor, dict):
                merchant_name = creditor.get('name', '')
            elif isinstance(debtor, dict):
                merchant_name = debtor.get('name', '')
            else:
                merchant_name = ''

            # Get description from remittance_information (which is a list)
            remittance_info = tx.get('remittance_information', [])
            if isinstance(remittance_info, list) and remittance_info:
                description = ' - '.join([str(r) for r in remittance_info if r])
            else:
                description = str(remittance_info) if remittance_info else ''

            # If no description, use merchant name
            if not description and merchant_name:
                description = merchant_name

            # Build normalized transaction
            normalized = {
                'external_id': tx.get('entry_reference') or tx.get('transaction_id'),
                'date': self._parse_date(tx.get('booking_date') or tx.get('value_date')),
                'booking_date': self._parse_date(tx.get('booking_date')),
                'value_date': self._parse_date(tx.get('value_date')),
                'amount': amount,
                'currency': tx_amount.get('currency', 'NOK'),
                'description': description.strip() if description else '',
                'reference': tx.get('reference_number') or '',
                'merchant_name': merchant_name.strip() if merchant_name else None,
                'raw_data': json.dumps(tx)  # Store full response for debugging
            }

            transactions.append(normalized)

        return transactions

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """
        Parse Enable Banking date string to Python date.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            date object or None if invalid
        """
        if not date_str:
            return None

        try:
            return date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None
