from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from decimal import Decimal

from backend.database import get_db
from ..models import BankAccount, User, Ledger, Transaction, JournalEntry, Account
from ..schemas import BankAccount as BankAccountSchema, BankAccountCreate, BankAccountUpdate
from ..auth import get_current_active_user, get_current_ledger
from ..opening_balance import set_opening_balance

router = APIRouter(prefix="/bank-accounts", tags=["bank-accounts"])


@router.get("/", response_model=List[BankAccountSchema])
def get_bank_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    return db.query(BankAccount).filter(
        BankAccount.ledger_id == current_ledger.id,
        BankAccount.is_active == True
    ).all()


@router.post("/", response_model=BankAccountSchema)
def create_bank_account(
    bank_account: BankAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    db_bank_account = BankAccount(
        ledger_id=current_ledger.id,
        **bank_account.model_dump()
    )
    db.add(db_bank_account)
    db.commit()
    db.refresh(db_bank_account)
    return db_bank_account


@router.get("/{bank_account_id}", response_model=BankAccountSchema)
def get_bank_account(
    bank_account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    bank_account = db.query(BankAccount).filter(
        BankAccount.id == bank_account_id,
        BankAccount.ledger_id == current_ledger.id
    ).first()
    if not bank_account:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return bank_account


@router.put("/{bank_account_id}", response_model=BankAccountSchema)
def update_bank_account(
    bank_account_id: int,
    updates: BankAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """
    Update bank account and optionally set opening balance.

    If opening_balance is provided, creates an IB (inngående balanse) transaction
    dated 2026-01-01 against the ledger's equity account. Re-sending it replaces
    the previous one.
    """
    bank_account = db.query(BankAccount).filter(
        BankAccount.id == bank_account_id,
        BankAccount.ledger_id == current_ledger.id
    ).first()
    if not bank_account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    # Update basic fields
    update_data = updates.model_dump(exclude_unset=True, exclude={'opening_balance'})
    for field, value in update_data.items():
        setattr(bank_account, field, value)

    # Handle opening balance if provided
    if updates.opening_balance is not None:
        account = db.query(Account).filter(Account.id == bank_account.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Tilknyttet konto ikke funnet")
        set_opening_balance(
            db=db,
            ledger_id=current_ledger.id,
            account=account,
            amount=updates.opening_balance,
            as_of=datetime(2026, 1, 1).date(),
            created_by=current_user.id,
            label=bank_account.name,
        )

    db.commit()
    db.refresh(bank_account)
    return bank_account


@router.delete("/{bank_account_id}")
def delete_bank_account(
    bank_account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """
    Delete (soft) bank account.

    Only allowed if there are no transactions on the account this year.
    """
    bank_account = db.query(BankAccount).filter(
        BankAccount.id == bank_account_id,
        BankAccount.ledger_id == current_ledger.id
    ).first()
    if not bank_account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    # Check for transactions this year
    current_year = datetime.now().year
    transactions_this_year = db.query(Transaction).join(JournalEntry).filter(
        Transaction.ledger_id == current_ledger.id,
        JournalEntry.account_id == bank_account.account_id,
        db.func.year(Transaction.transaction_date) == current_year
    ).count()

    if transactions_this_year > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Kan ikke slette konto med {transactions_this_year} transaksjoner i {current_year}"
        )

    bank_account.is_active = False
    db.commit()
    return {"message": "Bank account deleted"}
