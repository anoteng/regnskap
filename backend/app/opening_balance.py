"""Opening balances (inngående balanse) for any account.

Lets a ledger start with balances that predate its first transaction — a home
bought years ago, a mortgage, each person's equity contribution — without
reconstructing the history behind them.

The counter-entry goes to the ledger's equity account, which differs by chart
template: the business template has 2050, the personal and family templates use
the 2900 series.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import (
    Account,
    AccountType,
    JournalEntry,
    Transaction,
    TransactionSource,
    TransactionStatus,
)

# Tried in order; the first that exists in the ledger is used
EQUITY_ACCOUNT_PREFERENCE = ("2050", "2902", "2900")

# Accounts whose natural balance sits on the debit side
DEBIT_NATURED = (AccountType.ASSET, AccountType.EXPENSE)


def find_equity_account(db: Session, ledger_id: int) -> Account:
    """The account an opening balance is booked against."""
    for number in EQUITY_ACCOUNT_PREFERENCE:
        account = db.query(Account).filter(
            Account.ledger_id == ledger_id,
            Account.account_number == number,
        ).first()
        if account:
            return account

    fallback = db.query(Account).filter(
        Account.ledger_id == ledger_id,
        Account.account_type == AccountType.EQUITY,
        Account.is_active == True,  # noqa: E712
    ).order_by(Account.account_number).first()
    if fallback:
        return fallback

    raise HTTPException(
        status_code=400,
        detail="Fant ingen egenkapitalkonto å føre inngående balanse mot."
    )


def set_opening_balance(
    db: Session,
    ledger_id: int,
    account: Account,
    amount: Decimal,
    as_of: date,
    created_by: Optional[int] = None,
    label: Optional[str] = None,
) -> Transaction:
    """Create or replace the opening balance for one account.

    `amount` is the balance as the user thinks of it: a positive figure sits on
    the account's natural side, so 2 400 000 on a mortgage is debt and
    5 000 000 on a property is value. A negative figure flips the side, which
    is what an overdrawn bank account needs.
    """
    if amount is None:
        raise HTTPException(status_code=400, detail="Beløp mangler.")

    equity = find_equity_account(db, ledger_id)
    if equity.id == account.id:
        raise HTTPException(
            status_code=400,
            detail="Kan ikke føre inngående balanse mot egenkapitalkontoen selv."
        )

    marker = f"IB:{account.id}"
    existing = db.query(Transaction).filter(
        Transaction.ledger_id == ledger_id,
        Transaction.source_reference == marker,
    ).first()
    if existing:
        # Replacing beats refusing: correcting a typo should not require the
        # user to hunt down and delete the transaction first
        db.query(JournalEntry).filter(
            JournalEntry.transaction_id == existing.id
        ).delete()
        db.delete(existing)
        db.flush()

    name = label or f"{account.account_number} {account.account_name}"
    transaction = Transaction(
        ledger_id=ledger_id,
        description=f"Inngående balanse - {name}",
        transaction_date=as_of,
        created_by=created_by,
        status=TransactionStatus.POSTED,
        source=TransactionSource.MANUAL,
        source_reference=marker,
        is_reconciled=False,
    )
    db.add(transaction)
    db.flush()

    on_debit_side = (account.account_type in DEBIT_NATURED) == (amount >= 0)
    magnitude = abs(Decimal(amount))

    db.add(JournalEntry(
        transaction_id=transaction.id,
        account_id=account.id,
        debit=magnitude if on_debit_side else Decimal("0.00"),
        credit=Decimal("0.00") if on_debit_side else magnitude,
        description=f"IB {name}",
    ))
    db.add(JournalEntry(
        transaction_id=transaction.id,
        account_id=equity.id,
        debit=Decimal("0.00") if on_debit_side else magnitude,
        credit=magnitude if on_debit_side else Decimal("0.00"),
        description=f"IB {name}",
    ))

    return transaction
