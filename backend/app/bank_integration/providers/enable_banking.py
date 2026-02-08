"""
Enable Banking Provider Implementation

Enable Banking is a PSD2-compliant API that provides access to European banks.
Requires mTLS (mutual TLS) authentication with client certificates.

Documentation: https://enablebanking.com/docs/api/reference/
"""

import httpx
import json
from typing import Dict, Any, List, Optional
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from .base import BaseBankProvider


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

    async def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        bank_id: Optional[str] = None
    ) -> str:
        """
        Generate Enable Banking OAuth authorization URL.

        Args:
            state: CSRF protection token
            redirect_uri: Callback URL
            bank_id: ASPSP identifier (e.g., 'NO_DNB' for DNB Norway)

        Returns:
            Full authorization URL

        Example:
            >>> url = await provider.get_authorization_url(
            ...     state="random-token",
            ...     redirect_uri="https://example.com/callback",
            ...     bank_id="NO_DNB"
            ... )
            >>> # Redirect user to this URL
        """
        params = {
            'response_type': 'code',
            'client_id': self.app_id,
            'redirect_uri': redirect_uri,
            'state': state,
            'scope': 'accounts transactions',
        }

        # ASPSP = Account Servicing Payment Service Provider (the bank)
        if bank_id:
            params['aspsp'] = bank_id

        # Construct URL
        base_url = self.config.authorization_url
        query_string = urlencode(params)

        return f"{base_url}?{query_string}"

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access/refresh tokens.

        Enable Banking uses standard OAuth2 token exchange with mTLS.

        Args:
            code: Authorization code from callback
            redirect_uri: Must match the one used in authorization

        Returns:
            {
                'access_token': str,
                'refresh_token': str,
                'expires_in': int,
                'token_type': 'Bearer'
            }

        Raises:
            httpx.HTTPStatusError: If token exchange fails
        """
        async with httpx.AsyncClient(
            timeout=60.0,
            cert=self.client_cert  # mTLS
        ) as client:
            response = await client.post(
                self.config.token_url,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': redirect_uri,
                    'client_id': self.app_id,
                },
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )

            response.raise_for_status()
            return response.json()

    async def refresh_access_token(
        self,
        refresh_token: str
    ) -> Dict[str, Any]:
        """
        Refresh an expired access token.

        Args:
            refresh_token: The refresh token

        Returns:
            {
                'access_token': str,
                'expires_in': int,
                'token_type': 'Bearer'
            }
        """
        async with httpx.AsyncClient(
            timeout=60.0,
            cert=self.client_cert
        ) as client:
            response = await client.post(
                self.config.token_url,
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': self.app_id,
                },
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )

            response.raise_for_status()
            return response.json()

    async def fetch_accounts(
        self,
        access_token: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch list of accounts from the bank.

        Args:
            access_token: Valid OAuth access token

        Returns:
            List of accounts with normalized structure
        """
        async with httpx.AsyncClient(
            timeout=60.0,
            cert=self.client_cert
        ) as client:
            response = await client.get(
                f"{self.config.api_base_url}/accounts",
                headers={
                    'Authorization': f'Bearer {access_token}'
                }
            )

            response.raise_for_status()
            data = response.json()

            # Normalize Enable Banking account format
            return self._normalize_accounts(data)

    async def fetch_transactions(
        self,
        access_token: str,
        account_id: str,
        from_date: date,
        to_date: date
    ) -> List[Dict[str, Any]]:
        """
        Fetch transactions for an account.

        Enable Banking returns transactions in 'booked' and 'pending' arrays.
        We only process 'booked' transactions.

        Args:
            access_token: Valid OAuth access token
            account_id: Account ID from Enable Banking
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)

        Returns:
            List of normalized transactions

        Example:
            >>> transactions = await provider.fetch_transactions(
            ...     access_token="token",
            ...     account_id="account123",
            ...     from_date=date(2024, 1, 1),
            ...     to_date=date(2024, 1, 31)
            ... )
            >>> print(f"Fetched {len(transactions)} transactions")
        """
        async with httpx.AsyncClient(
            timeout=60.0,
            cert=self.client_cert
        ) as client:
            response = await client.get(
                f"{self.config.api_base_url}/accounts/{account_id}/transactions",
                params={
                    'dateFrom': from_date.isoformat(),
                    'dateTo': to_date.isoformat()
                },
                headers={
                    'Authorization': f'Bearer {access_token}'
                }
            )

            response.raise_for_status()
            data = response.json()

            # Normalize Enable Banking transaction format
            return self._normalize_transactions(data)

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

        Enable Banking format:
        {
            "accounts": [
                {
                    "resourceId": "account-id",
                    "name": "Main Account",
                    "iban": "NO1234567890",
                    "bic": "DNBANOKK",
                    "currency": "NOK",
                    "product": "Current Account"
                }
            ]
        }

        Args:
            api_response: Raw response from Enable Banking

        Returns:
            Normalized account list
        """
        accounts = []

        for account in api_response.get('accounts', []):
            accounts.append({
                'account_id': account.get('resourceId'),
                'account_name': account.get('name') or account.get('product', 'Unknown'),
                'iban': account.get('iban'),
                'bic': account.get('bic'),
                'currency': account.get('currency', 'NOK'),
                'account_type': account.get('product', 'CHECKING')
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
        transactions = []

        # Only process booked transactions (not pending)
        booked = api_response.get('transactions', {}).get('booked', [])

        for tx in booked:
            # Parse amount
            tx_amount = tx.get('transactionAmount', {})
            amount_str = tx_amount.get('amount', '0')
            amount = Decimal(str(amount_str))

            # Get merchant name (creditor for payments out, debtor for payments in)
            merchant_name = tx.get('creditorName') or tx.get('debtorName')

            # Get description (remittanceInformationUnstructured is the main description field)
            description = tx.get('remittanceInformationUnstructured', '')
            if not description and merchant_name:
                description = merchant_name

            # Build normalized transaction
            normalized = {
                'external_id': tx.get('transactionId'),
                'date': self._parse_date(tx.get('valueDate') or tx.get('bookingDate')),
                'booking_date': self._parse_date(tx.get('bookingDate')),
                'value_date': self._parse_date(tx.get('valueDate')),
                'amount': amount,
                'currency': tx_amount.get('currency', 'NOK'),
                'description': description.strip() if description else '',
                'reference': tx.get('endToEndId') or tx.get('mandateId') or '',
                'merchant_name': merchant_name,
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
