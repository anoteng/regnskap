"""Planned transactions: created from registered invoices, matched against bank sync.

An INVOICE attachment with due_date and amount produces one planned transaction.
Bank sync auto-matches incoming payments conservatively (exact amount, date near
due date, unambiguous candidate). Everything else is left for manual matching.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from .models import (
    Account,
    AttachmentType,
    PlannedTransaction,
    PlannedTransactionStatus,
    Receipt,
    ReceiptStatus,
    Transaction,
)

# Payment may leave the account up to this many days before the due date...
MATCH_DAYS_BEFORE_DUE = 10
# ...or this many days after (late payment)
MATCH_DAYS_AFTER_DUE = 7
AMOUNT_TOLERANCE = Decimal("0.01")


def sync_planned_from_receipt(
    db: Session, receipt: Receipt, created_by: Optional[int] = None
) -> Optional[PlannedTransaction]:
    """Create or update the planned transaction belonging to an invoice receipt.

    Idempotent: each receipt has at most one planned transaction. If the receipt
    no longer qualifies (type changed away from INVOICE, or due date/amount
    removed), an OPEN plan is cancelled. A MATCHED plan is never modified.
    """
    planned = db.query(PlannedTransaction).filter(
        PlannedTransaction.receipt_id == receipt.id
    ).first()

    qualifies = (
        receipt.attachment_type == AttachmentType.INVOICE
        and receipt.due_date is not None
        and receipt.amount is not None
    )

    if not qualifies:
        if planned and planned.status == PlannedTransactionStatus.OPEN:
            planned.status = PlannedTransactionStatus.CANCELLED
        return planned

    description = (
        receipt.description
        or receipt.ai_extracted_vendor
        or receipt.original_filename
        or "Faktura"
    )

    suggested_account_id = None
    if receipt.ai_suggested_account:
        account = db.query(Account).filter(
            Account.ledger_id == receipt.ledger_id,
            Account.account_number == receipt.ai_suggested_account,
        ).first()
        if account:
            suggested_account_id = account.id

    if planned is None:
        planned = PlannedTransaction(
            ledger_id=receipt.ledger_id,
            receipt_id=receipt.id,
            description=description,
            expected_date=receipt.due_date,
            amount=receipt.amount,
            suggested_account_id=suggested_account_id,
            status=PlannedTransactionStatus.OPEN,
            created_by=created_by,
        )
        db.add(planned)
    elif planned.status != PlannedTransactionStatus.MATCHED:
        planned.description = description
        planned.expected_date = receipt.due_date
        planned.amount = receipt.amount
        planned.suggested_account_id = suggested_account_id
        planned.status = PlannedTransactionStatus.OPEN

    return planned


def mark_planned_matched(
    db: Session,
    planned: PlannedTransaction,
    transaction: Transaction,
    matched_by: Optional[int] = None,
) -> None:
    """Mark a planned transaction (and its invoice) as settled by a transaction."""
    planned.status = PlannedTransactionStatus.MATCHED
    planned.matched_transaction_id = transaction.id

    if planned.receipt and planned.receipt.status == ReceiptStatus.PENDING:
        planned.receipt.status = ReceiptStatus.MATCHED
        planned.receipt.matched_transaction_id = transaction.id
        planned.receipt.matched_at = datetime.utcnow()
        planned.receipt.matched_by = matched_by


def reopen_planned_for_receipt(db: Session, receipt_id: int) -> None:
    """Reopen the plan when its invoice is unmatched from a transaction."""
    planned = db.query(PlannedTransaction).filter(
        PlannedTransaction.receipt_id == receipt_id,
        PlannedTransaction.status == PlannedTransactionStatus.MATCHED,
    ).first()
    if planned:
        planned.status = PlannedTransactionStatus.OPEN
        planned.matched_transaction_id = None


def find_and_match_for_bank_transaction(
    db: Session,
    transaction: Transaction,
    amount_out: Decimal,
    ledger_id: int,
) -> Optional[PlannedTransaction]:
    """Auto-match a freshly imported outgoing bank transaction against open plans.

    Conservative on purpose: exact amount, transaction date within the payment
    window around the due date, and a single clear winner. Ambiguity leaves the
    plan open for manual matching instead of guessing.
    """
    tx_date = transaction.transaction_date

    candidates = db.query(PlannedTransaction).filter(
        PlannedTransaction.ledger_id == ledger_id,
        PlannedTransaction.status == PlannedTransactionStatus.OPEN,
        PlannedTransaction.expected_date >= tx_date - timedelta(days=MATCH_DAYS_AFTER_DUE),
        PlannedTransaction.expected_date <= tx_date + timedelta(days=MATCH_DAYS_BEFORE_DUE),
    ).all()

    matches = [
        p for p in candidates
        if abs(Decimal(p.amount) - amount_out) <= AMOUNT_TOLERANCE
    ]
    if not matches:
        return None

    matches.sort(key=lambda p: abs((p.expected_date - tx_date).days))
    if len(matches) > 1:
        best = abs((matches[0].expected_date - tx_date).days)
        runner_up = abs((matches[1].expected_date - tx_date).days)
        if best == runner_up:
            return None

    planned = matches[0]
    mark_planned_matched(db, planned, transaction)
    return planned
