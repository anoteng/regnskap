"""Market value adjustments (verdiregulering) for investment accounts.

A fund account drifts away from its book value the moment it is funded: the
ledger knows what was paid in, the market knows what it is worth. Recording a
current value closes that gap and leaves a dated trail, so the ups and downs
stay visible instead of being folded into one opaque figure.

The counter-entry goes to the account's own `value_change_account_id`, which
lets separate pots be kept apart — own funds, locked pension, a child's
savings — without the caller having to know which is which.

Adjustments must be entered in chronological order. An earlier one inserted
after the fact would invalidate every later amount, since each was derived
from the balance at the time; refusing is better than silently recomputing a
chain the user cannot see.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import (
    Account,
    AccountType,
    JournalEntry,
    Transaction,
    TransactionSource,
    TransactionStatus,
)

# Used when an account has no value_change_account_id of its own
VALUE_CHANGE_PREFERENCE = ("8300", "8000")

BOOKED = (TransactionStatus.POSTED, TransactionStatus.RECONCILED)


def marker_for(account_id: int, as_of: date) -> str:
    return f"VR:{account_id}:{as_of.isoformat()}"


def find_value_change_account(db: Session, account: Account) -> Account:
    """The account a value change is booked against."""
    if account.value_change_account_id:
        target = db.query(Account).filter(
            Account.id == account.value_change_account_id,
            Account.ledger_id == account.ledger_id,
        ).first()
        if target:
            return target

    for number in VALUE_CHANGE_PREFERENCE:
        target = db.query(Account).filter(
            Account.ledger_id == account.ledger_id,
            Account.account_number == number,
        ).first()
        if target:
            return target

    raise HTTPException(
        status_code=400,
        detail="Fant ingen konto for verdiendring. Opprett 8300 eller velg en "
               "motkonto på kontoen.",
    )


def balance_at(db: Session, account_id: int, as_of: date) -> Decimal:
    """Booked balance on the account's natural side, up to and including a date."""
    total = db.query(
        func.coalesce(func.sum(JournalEntry.debit - JournalEntry.credit), 0)
    ).join(
        Transaction, Transaction.id == JournalEntry.transaction_id
    ).filter(
        JournalEntry.account_id == account_id,
        Transaction.status.in_(BOOKED),
        Transaction.transaction_date <= as_of,
    ).scalar()
    return Decimal(total or 0)


def adjustments_for(db: Session, account_id: int) -> List[Transaction]:
    return db.query(Transaction).filter(
        Transaction.source_reference.like(f"VR:{account_id}:%")
    ).order_by(Transaction.transaction_date).all()


def set_market_value(
    db: Session,
    ledger_id: int,
    account: Account,
    value: Decimal,
    as_of: date,
    created_by: Optional[int] = None,
) -> Optional[Transaction]:
    """Adjust an account to `value` as of a date.

    Returns the adjustment, or None when the account already stands at that
    value and no entry is needed.
    """
    if account.account_type != AccountType.ASSET:
        raise HTTPException(
            status_code=400,
            detail="Verdiregulering gjelder bare eiendelskontoer.",
        )
    if value is None:
        raise HTTPException(status_code=400, detail="Verdi mangler.")

    counter = find_value_change_account(db, account)
    if counter.id == account.id:
        raise HTTPException(
            status_code=400,
            detail="Kontoen kan ikke være sin egen motkonto.",
        )

    marker = marker_for(account.id, as_of)

    later = db.query(Transaction).filter(
        Transaction.source_reference.like(f"VR:{account.id}:%"),
        Transaction.transaction_date > as_of,
    ).order_by(Transaction.transaction_date).first()
    if later:
        raise HTTPException(
            status_code=400,
            detail=f"Det finnes allerede en verdiregulering datert "
                   f"{later.transaction_date.isoformat()}. Nye verdier må være "
                   f"datert samme dag eller senere.",
        )

    # Replacing beats refusing: a typo should not need a detour via deletion
    existing = db.query(Transaction).filter(
        Transaction.ledger_id == ledger_id,
        Transaction.source_reference == marker,
    ).first()
    if existing:
        db.query(JournalEntry).filter(
            JournalEntry.transaction_id == existing.id
        ).delete()
        db.delete(existing)
        db.flush()

    target = Decimal(value)
    difference = target - balance_at(db, account.id, as_of)
    if difference == 0:
        return None

    magnitude = abs(difference)
    on_debit_side = difference > 0
    name = f"{account.account_number} {account.account_name}"

    transaction = Transaction(
        ledger_id=ledger_id,
        description=f"Verdiregulering - {name}",
        transaction_date=as_of,
        created_by=created_by,
        status=TransactionStatus.POSTED,
        source=TransactionSource.MANUAL,
        source_reference=marker,
        is_reconciled=False,
    )
    db.add(transaction)
    db.flush()

    db.add(JournalEntry(
        transaction_id=transaction.id,
        account_id=account.id,
        debit=magnitude if on_debit_side else Decimal("0.00"),
        credit=Decimal("0.00") if on_debit_side else magnitude,
        description=f"Til markedsverdi {target:.2f}",
    ))
    db.add(JournalEntry(
        transaction_id=transaction.id,
        account_id=counter.id,
        debit=Decimal("0.00") if on_debit_side else magnitude,
        credit=magnitude if on_debit_side else Decimal("0.00"),
        description=f"Verdiendring {account.account_number}",
    ))

    return transaction
