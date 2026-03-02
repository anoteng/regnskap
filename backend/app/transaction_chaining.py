"""
Transaction Chaining Module

Detects pairs of DRAFT bank-synced transactions that represent two sides
of the same inter-account transfer (e.g., credit card payment from checking
account) and merges them into a single balanced transaction.
"""

from decimal import Decimal
from datetime import date
from typing import List
from sqlalchemy.orm import Session, joinedload

from backend.app.models import (
    Transaction, JournalEntry, BankTransaction,
    TransactionStatus, TransactionSource,
    BankTransactionImportStatus
)


class ChainSuggestion:
    """A suggested pair of transactions to chain together."""

    def __init__(
        self,
        primary_transaction_id: int,
        secondary_transaction_id: int,
        primary_description: str,
        secondary_description: str,
        primary_account_name: str,
        secondary_account_name: str,
        amount: Decimal,
        primary_date: date,
        secondary_date: date,
        confidence: str
    ):
        self.primary_transaction_id = primary_transaction_id
        self.secondary_transaction_id = secondary_transaction_id
        self.primary_description = primary_description
        self.secondary_description = secondary_description
        self.primary_account_name = primary_account_name
        self.secondary_account_name = secondary_account_name
        self.amount = amount
        self.primary_date = primary_date
        self.secondary_date = secondary_date
        self.confidence = confidence


class TransactionChainMatcher:
    """
    Finds pairs of DRAFT BANK_SYNC transactions that are likely
    two sides of the same inter-account transfer.
    """

    @staticmethod
    def find_chain_candidates(db: Session, ledger_id: int) -> List[ChainSuggestion]:
        # Get all chainable transactions: DRAFT + BANK_SYNC
        chainable = db.query(Transaction).options(
            joinedload(Transaction.journal_entries).joinedload(JournalEntry.account)
        ).filter(
            Transaction.ledger_id == ledger_id,
            Transaction.status == TransactionStatus.DRAFT,
            Transaction.source == TransactionSource.BANK_SYNC
        ).all()

        # Filter to exactly 1 journal entry
        singles = [t for t in chainable if len(t.journal_entries) == 1]

        # Split into debits and credits
        debits = []
        credits = []

        for t in singles:
            entry = t.journal_entries[0]
            if entry.debit > 0 and entry.credit == 0:
                debits.append((t, entry))
            elif entry.credit > 0 and entry.debit == 0:
                credits.append((t, entry))

        # Match debits to credits
        suggestions = []
        used_credit_ids = set()

        for dt, de in debits:
            best_match = None
            best_date_diff = 999

            for ct, ce in credits:
                if ct.id in used_credit_ids:
                    continue
                if de.account_id == ce.account_id:
                    continue  # Same account, not an inter-account transfer
                if de.debit != ce.credit:
                    continue  # Amount mismatch

                date_diff = abs((dt.transaction_date - ct.transaction_date).days)
                if date_diff > 2:
                    continue

                # Prefer closest date match
                if date_diff < best_date_diff:
                    best_match = (ct, ce)
                    best_date_diff = date_diff

            if best_match:
                ct, ce = best_match
                confidence = "HIGH" if best_date_diff == 0 else "MEDIUM"

                # Primary = earlier date (or debit side if same date)
                if dt.transaction_date <= ct.transaction_date:
                    primary, secondary = dt, ct
                    primary_entry, secondary_entry = de, ce
                else:
                    primary, secondary = ct, dt
                    primary_entry, secondary_entry = ce, de

                suggestions.append(ChainSuggestion(
                    primary_transaction_id=primary.id,
                    secondary_transaction_id=secondary.id,
                    primary_description=primary.description,
                    secondary_description=secondary.description,
                    primary_account_name=primary_entry.account.account_name if primary_entry.account else "Ukjent",
                    secondary_account_name=secondary_entry.account.account_name if secondary_entry.account else "Ukjent",
                    amount=de.debit,
                    primary_date=primary.transaction_date,
                    secondary_date=secondary.transaction_date,
                    confidence=confidence
                ))

                used_credit_ids.add(ct.id)

        # Sort: HIGH confidence first, then by date descending
        suggestions.sort(key=lambda s: (
            0 if s.confidence == "HIGH" else 1,
            -s.primary_date.toordinal()
        ))

        return suggestions

    @staticmethod
    def chain_transactions(
        db: Session,
        ledger_id: int,
        primary_id: int,
        secondary_id: int,
        auto_post: bool = False
    ) -> Transaction:
        """
        Merge two DRAFT transactions into one balanced transaction.

        Moves the journal entry from secondary to primary, updates
        BankTransaction references, and deletes the secondary.
        """
        # Load both transactions with their journal entries
        primary = db.query(Transaction).options(
            joinedload(Transaction.journal_entries).joinedload(JournalEntry.account)
        ).filter(
            Transaction.id == primary_id,
            Transaction.ledger_id == ledger_id
        ).first()

        secondary = db.query(Transaction).options(
            joinedload(Transaction.journal_entries)
        ).filter(
            Transaction.id == secondary_id,
            Transaction.ledger_id == ledger_id
        ).first()

        if not primary:
            raise ValueError("Primærtransaksjon ikke funnet")
        if not secondary:
            raise ValueError("Sekundærtransaksjon ikke funnet")

        if primary.status != TransactionStatus.DRAFT:
            raise ValueError("Primærtransaksjon er ikke i DRAFT-status")
        if secondary.status != TransactionStatus.DRAFT:
            raise ValueError("Sekundærtransaksjon er ikke i DRAFT-status")

        if len(primary.journal_entries) != 1:
            raise ValueError("Primærtransaksjon må ha nøyaktig 1 postering")
        if len(secondary.journal_entries) != 1:
            raise ValueError("Sekundærtransaksjon må ha nøyaktig 1 postering")

        secondary_entry_id = secondary.journal_entries[0].id
        secondary_tx_id = secondary.id

        # Use raw SQL UPDATE to move journal entry - avoids SQLAlchemy's
        # delete-orphan cascade which would delete the entry when it's
        # removed from secondary's collection
        db.query(JournalEntry).filter(
            JournalEntry.id == secondary_entry_id
        ).update({"transaction_id": primary.id})

        # Update BankTransaction references pointing to secondary
        db.query(BankTransaction).filter(
            BankTransaction.imported_transaction_id == secondary_tx_id
        ).update({"imported_transaction_id": primary.id})

        # Expunge secondary from session to prevent cascade deleting the
        # journal entry we just moved
        db.expunge(secondary)

        # Delete the secondary transaction (now has 0 journal entries)
        db.query(Transaction).filter(Transaction.id == secondary_tx_id).delete()

        # Flush and reload primary with updated entries
        db.flush()
        db.expire(primary)

        primary = db.query(Transaction).options(
            joinedload(Transaction.journal_entries).joinedload(JournalEntry.account)
        ).filter(Transaction.id == primary_id).first()

        # Check if balanced and auto-post if requested
        total_debit = sum(e.debit for e in primary.journal_entries)
        total_credit = sum(e.credit for e in primary.journal_entries)
        is_balanced = abs(total_debit - total_credit) < Decimal("0.01")

        if auto_post and is_balanced and len(primary.journal_entries) >= 2:
            primary.status = TransactionStatus.POSTED

        db.commit()

        return primary
