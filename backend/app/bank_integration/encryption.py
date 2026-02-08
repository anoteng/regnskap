"""
Token Encryption Module

Provides encryption and decryption for OAuth tokens using Fernet symmetric encryption.
Uses the SECRET_KEY from environment variables for the encryption key.
"""

from cryptography.fernet import Fernet
import base64
import os


class TokenEncryption:
    """
    Encrypt and decrypt OAuth tokens for secure storage in database.

    Uses Fernet (symmetric encryption) with the SECRET_KEY from environment.
    All tokens are encrypted before storage and decrypted when needed.
    """

    def __init__(self):
        """
        Initialize encryption cipher using SECRET_KEY from environment.

        The SECRET_KEY is padded/truncated to 32 bytes and base64-encoded
        to create a valid Fernet key.
        """
        # Get SECRET_KEY from environment
        secret_key = os.getenv('SECRET_KEY', 'default-secret-key-change-in-production')

        # Fernet requires 32-byte key, base64-encoded
        # Pad or truncate secret_key to 32 bytes
        key_bytes = secret_key.encode()[:32].ljust(32, b'0')
        key_base64 = base64.urlsafe_b64encode(key_bytes)

        # Create Fernet cipher
        self.cipher = Fernet(key_base64)

    def encrypt(self, token: str) -> str:
        """
        Encrypt a token for database storage.

        Args:
            token: Plain text token to encrypt

        Returns:
            Base64-encoded encrypted token suitable for TEXT column

        Example:
            >>> enc = TokenEncryption()
            >>> encrypted = enc.encrypt("sk-abc123")
            >>> # Store encrypted in database
        """
        if not token:
            return ""

        # Encrypt token
        encrypted_bytes = self.cipher.encrypt(token.encode())

        # Base64 encode for database storage (TEXT column)
        return base64.b64encode(encrypted_bytes).decode()

    def decrypt(self, encrypted_token: str) -> str:
        """
        Decrypt a token from database.

        Args:
            encrypted_token: Base64-encoded encrypted token from database

        Returns:
            Plain text token

        Example:
            >>> enc = TokenEncryption()
            >>> token = enc.decrypt(encrypted_from_db)
            >>> # Use token for API calls
        """
        if not encrypted_token:
            return ""

        # Decode from base64
        encrypted_bytes = base64.b64decode(encrypted_token)

        # Decrypt
        decrypted_bytes = self.cipher.decrypt(encrypted_bytes)

        return decrypted_bytes.decode()

    def is_encrypted(self, value: str) -> bool:
        """
        Check if a value appears to be encrypted.

        This is a heuristic check based on base64 format and length.
        Not 100% accurate but useful for migration/debugging.

        Args:
            value: String to check

        Returns:
            True if value looks encrypted
        """
        if not value or len(value) < 50:  # Encrypted tokens are typically longer
            return False

        try:
            # Try to decode as base64
            base64.b64decode(value)
            return True
        except Exception:
            return False
