from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from ..models import BankAccount, User, Ledger
from ..schemas import BankAccount as BankAccountSchema, BankAccountCreate
from ..auth import get_current_active_user, get_current_ledger

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


@router.delete("/{bank_account_id}")
def delete_bank_account(
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

    bank_account.is_active = False
    db.commit()
    return {"message": "Bank account deleted"}
