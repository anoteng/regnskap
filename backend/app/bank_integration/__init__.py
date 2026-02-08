"""
Bank Integration Module

Provides multi-provider bank API integration for automatic transaction sync.
Supports Enable Banking, Tink, and Neonomics with extensible provider architecture.
"""

from .service import BankIntegrationService
from .encryption import TokenEncryption
from .deduplication import TransactionDeduplicator

__all__ = ['BankIntegrationService', 'TokenEncryption', 'TransactionDeduplicator']
