"""
Abstract base class for bank integration providers

Defines the common interface that all bank API providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import date
import json


class BaseBankProvider(ABC):
    """
    Abstract base class for bank integration providers.

    All concrete providers (Enable Banking, Tink, Neonomics) must implement
    these methods to ensure consistent behavior across different banking APIs.
    """

    def __init__(self, provider_config):
        """
        Initialize provider with configuration from database.

        Args:
            provider_config: BankProvider model instance with configuration
        """
        self.config = provider_config

        # Parse JSON configuration data
        try:
            self.config_data = json.loads(provider_config.config_data) if provider_config.config_data else {}
        except (json.JSONDecodeError, TypeError):
            self.config_data = {}

    @abstractmethod
    async def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        bank_id: Optional[str] = None
    ) -> str:
        """
        Generate OAuth authorization URL for user to authorize bank access.

        Args:
            state: CSRF protection token
            redirect_uri: Where to redirect after authorization
            bank_id: Optional specific bank/ASPSP identifier

        Returns:
            Full authorization URL to redirect user to
        """
        pass

    @abstractmethod
    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access/refresh tokens.

        Args:
            code: Authorization code from OAuth callback
            redirect_uri: Must match the one used in authorization

        Returns:
            Dictionary with keys:
            - access_token: str
            - refresh_token: str (optional)
            - expires_in: int (seconds until expiry)
            - token_type: str (usually 'Bearer')
        """
        pass

    @abstractmethod
    async def refresh_access_token(
        self,
        refresh_token: str
    ) -> Dict[str, Any]:
        """
        Refresh an expired access token using refresh token.

        Args:
            refresh_token: The refresh token

        Returns:
            Dictionary with new access_token and expires_in
        """
        pass

    @abstractmethod
    async def fetch_accounts(
        self,
        access_token: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch list of accounts available from the bank.

        Args:
            access_token: Valid OAuth access token

        Returns:
            List of account dictionaries with keys:
            - account_id: str (provider's account identifier)
            - account_name: str
            - iban: str (optional)
            - bic: str (optional)
            - currency: str
            - account_type: str
        """
        pass

    @abstractmethod
    async def fetch_transactions(
        self,
        access_token: str,
        account_id: str,
        from_date: date,
        to_date: date
    ) -> List[Dict[str, Any]]:
        """
        Fetch transactions for an account within date range.

        Args:
            access_token: Valid OAuth access token
            account_id: Account identifier from provider
            from_date: Start date (inclusive)
            to_date: End date (inclusive)

        Returns:
            List of normalized transaction dictionaries with keys:
            - external_id: str (unique transaction ID from provider)
            - date: date (transaction date)
            - booking_date: date (optional)
            - value_date: date (optional)
            - amount: Decimal
            - currency: str
            - description: str
            - reference: str (optional)
            - merchant_name: str (optional)
            - raw_data: str (full JSON response)
        """
        pass

    @abstractmethod
    async def revoke_token(
        self,
        access_token: str
    ) -> bool:
        """
        Revoke access token (disconnect bank).

        Args:
            access_token: Token to revoke

        Returns:
            True if revocation successful
        """
        pass

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Helper to get configuration value from config_data JSON.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config_data.get(key, default)
