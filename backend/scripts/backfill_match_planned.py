"""One-off: match backfilled OPEN planned transactions against existing
transactions. Same conservative rules as the bank sync auto-match: exact
amount, date within the payment window, single unambiguous candidate.

Run from repo root: venv/bin/python -m backend.scripts.backfill_match_planned
"""
from datetime import timedelta
from decimal import Decimal

from backend.database import SessionLocal
from backend.app.models import (
    Account, AccountType, JournalEntry, PlannedTransaction,
    PlannedTransactionStatus, Transaction, TransactionStatus,
)
from backend.app.planned_transactions import (
    AMOUNT_TOLERANCE, MATCH_DAYS_AFTER_DUE, MATCH_DAYS_BEFORE_DUE,
    mark_planned_matched,
)


def main():
    db = SessionLocal()
    try:
        open_plans = db.query(PlannedTransaction).filter(
            PlannedTransaction.status == PlannedTransactionStatus.OPEN
        ).all()

        for planned in open_plans:
            date_from = planned.expected_date - timedelta(days=MATCH_DAYS_BEFORE_DUE)
            date_to = planned.expected_date + timedelta(days=MATCH_DAYS_AFTER_DUE)

            candidates = (
                db.query(Transaction)
                .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
                .join(Account, Account.id == JournalEntry.account_id)
                .filter(
                    Transaction.ledger_id == planned.ledger_id,
                    Transaction.transaction_date >= date_from,
                    Transaction.transaction_date <= date_to,
                    Account.account_type == AccountType.ASSET,
                    JournalEntry.credit >= Decimal(planned.amount) - AMOUNT_TOLERANCE,
                    JournalEntry.credit <= Decimal(planned.amount) + AMOUNT_TOLERANCE,
                )
                .distinct()
                .all()
            )

            if len(candidates) == 1:
                tx = candidates[0]
                mark_planned_matched(db, planned, tx)
                print(f"MATCHED planned {planned.id} ({planned.description!r}, "
                      f"{planned.amount} due {planned.expected_date}) -> tx {tx.id} "
                      f"({tx.transaction_date} {tx.description!r})")
            else:
                print(f"SKIPPED planned {planned.id} ({planned.description!r}, "
                      f"{planned.amount} due {planned.expected_date}): "
                      f"{len(candidates)} candidates")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
