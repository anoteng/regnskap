"""
Transaction Deduplication Module

Handles detection of duplicate transactions using multi-level strategy:
1. External transaction ID (fastest)
2. Hash-based matching (main strategy)
3. Fuzzy matching (future enhancement)
"""

import hashlib
from decimal import Decimal
from datetime import date, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from backend.app.models import Transaction, JournalEntry, BankTransaction


class TransactionDeduplicator:
    """
    Handle transaction deduplication across multiple sources.

    Prevents importing the same transaction multiple times from:
    - Multiple bank syncs of same date range
    - CSV import + bank sync
    - Manual entry + bank sync
    """

    @staticmethod
    def generate_hash(
        transaction_date: date,
        amount: Decimal,
        description: str,
        reference: Optional[str] = None
    ) -> str:
        """
        Generate deduplication hash from transaction attributes.

        Uses MD5 for speed (not security). Hash is deterministic so
        same transaction always generates same hash.

        Args:
            transaction_date: Transaction date
            amount: Transaction amount
            description: Transaction description
            reference: Optional reference number

        Returns:
            32-character hex MD5 hash

        Example:
            >>> hash1 = TransactionDeduplicator.generate_hash(
            ...     date(2024, 1, 15),
            ...     Decimal("123.45"),
            ...     "Coffee Shop",
            ...     "REF123"
            ... )
            >>> # Same transaction will always generate same hash
        """
        # Normalize inputs to ensure consistent hashing
        date_str = transaction_date.isoformat()  # YYYY-MM-DD
        amount_str = f"{amount:.2f}"  # Always 2 decimals
        desc_normalized = description.strip().lower()[:200]  # Truncate, lowercase
        ref_normalized = (reference or '').strip().lower()[:100]

        # Create hash input string
        hash_input = f"{date_str}|{amount_str}|{desc_normalized}|{ref_normalized}"

        # Generate MD5 hash (fast, not cryptographic)
        return hashlib.md5(hash_input.encode()).hexdigest()

    @staticmethod
    def find_duplicate_transaction(
        db: Session,
        ledger_id: int,
        bank_account_id: int,
        dedup_hash: str,
        transaction_date: date,
        amount: Decimal
    ) -> Optional[Transaction]:
        """
        Check if transaction already exists in the system.

        Searches existing transactions by:
        1. Same ledger
        2. Same bank account (via journal entries)
        3. Similar date (±3 days for booking/value date differences)
        4. Same amount
        5. Matching hash (description/reference similarity)

        Args:
            db: Database session
            ledger_id: Ledger to search in
            bank_account_id: Bank account's GL account ID
            dedup_hash: Hash to match against
            transaction_date: Transaction date
            amount: Transaction amount

        Returns:
            Matching Transaction if found, None otherwise

        Example:
            >>> duplicate = TransactionDeduplicator.find_duplicate_transaction(
            ...     db, ledger_id=1, bank_account_id=5,
            ...     dedup_hash="abc123...", transaction_date=date.today(),
            ...     amount=Decimal("100.00")
            ... )
            >>> if duplicate:
            ...     print(f"Already imported as transaction #{duplicate.id}")
        """
        # Search in date range (±3 days for booking vs value date differences)
        date_from = transaction_date - timedelta(days=3)
        date_to = transaction_date + timedelta(days=3)

        # Find transactions with matching amount in date range
        # Must have journal entry for the specific bank account
        candidates = db.query(Transaction).join(
            JournalEntry,
            JournalEntry.transaction_id == Transaction.id
        ).filter(
            and_(
                Transaction.ledger_id == ledger_id,
                JournalEntry.account_id == bank_account_id,
                Transaction.transaction_date >= date_from,
                Transaction.transaction_date <= date_to,
                or_(
                    JournalEntry.debit == abs(amount),
                    JournalEntry.credit == abs(amount)
                )
            )
        ).all()

        # For each candidate, generate hash and compare
        for tx in candidates:
            # Generate hash for existing transaction
            tx_hash = TransactionDeduplicator.generate_hash(
                tx.transaction_date,
                amount,  # Use same amount (sign doesn't matter)
                tx.description,
                tx.reference
            )

            # If hashes match, it's a duplicate
            if tx_hash == dedup_hash:
                return tx

        return None

    @staticmethod
    def check_duplicate_bank_transaction(
        db: Session,
        bank_connection_id: int,
        external_id: str,
        dedup_hash: str
    ) -> Optional[BankTransaction]:
        """
        Check if bank transaction was already fetched.

        Uses both external_id (fast unique check) and dedup_hash (for
        detecting duplicates across different connections).

        Args:
            db: Database session
            bank_connection_id: Bank connection ID
            external_id: External transaction ID from provider
            dedup_hash: Deduplication hash

        Returns:
            Existing BankTransaction if found, None otherwise

        Example:
            >>> existing = TransactionDeduplicator.check_duplicate_bank_transaction(
            ...     db, connection_id=1, external_id="TX123", dedup_hash="abc..."
            ... )
            >>> if existing:
            ...     print(f"Already fetched at {existing.fetched_at}")
        """
        # First check by external_id (fastest, unique constraint)
        existing = db.query(BankTransaction).filter(
            and_(
                BankTransaction.bank_connection_id == bank_connection_id,
                BankTransaction.external_transaction_id == external_id
            )
        ).first()

        if existing:
            return existing

        # Fallback: check by dedup_hash
        # Useful if provider changes external_id format or user has multiple connections
        existing = db.query(BankTransaction).filter(
            and_(
                BankTransaction.bank_connection_id == bank_connection_id,
                BankTransaction.dedup_hash == dedup_hash
            )
        ).first()

        return existing

    @staticmethod
    def mark_as_duplicate(
        db: Session,
        bank_transaction_id: int,
        duplicate_transaction_id: int
    ):
        """
        Mark a bank transaction as duplicate of existing transaction.

        Updates the bank_transaction record to indicate it was already
        imported or manually created.

        Args:
            db: Database session
            bank_transaction_id: BankTransaction to mark as duplicate
            duplicate_transaction_id: Existing Transaction it duplicates
        """
        bank_tx = db.query(BankTransaction).get(bank_transaction_id)
        if bank_tx:
            bank_tx.import_status = 'DUPLICATE'
            bank_tx.imported_transaction_id = duplicate_transaction_id
            db.commit()
