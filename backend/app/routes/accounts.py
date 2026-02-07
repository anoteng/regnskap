from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from ..models import Account, User, Ledger, BankAccount, JournalEntry, LedgerAccountSettings
from ..schemas import Account as AccountSchema, AccountCreate
from ..auth import get_current_active_user, get_current_ledger

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/", response_model=List[AccountSchema])
def get_accounts(
    skip: int = 0,
    limit: int = 1000,
    account_type: str = None,
    show_hidden: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    query = db.query(Account).filter(Account.is_active == True)
    if account_type:
        query = query.filter(Account.account_type == account_type.upper())

    # Filter out hidden accounts for this ledger unless explicitly requested
    if not show_hidden:
        # Get hidden account IDs for this ledger
        hidden_settings = db.query(LedgerAccountSettings).filter(
            LedgerAccountSettings.ledger_id == current_ledger.id,
            LedgerAccountSettings.is_hidden == True
        ).all()
        hidden_ids = [s.account_id for s in hidden_settings]

        if hidden_ids:
            query = query.filter(~Account.id.in_(hidden_ids))

    accounts = query.offset(skip).limit(limit).all()
    return accounts


@router.post("/", response_model=AccountSchema)
def create_account(
    account: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    existing = db.query(Account).filter(Account.account_number == account.account_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Account number already exists")

    db_account = Account(
        account_number=account.account_number,
        account_name=account.account_name,
        account_type=account.account_type,
        parent_account_id=account.parent_account_id,
        description=account.description,
        is_system=False,
        is_active=True
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account


@router.get("/{account_id}", response_model=AccountSchema)
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.put("/{account_id}", response_model=AccountSchema)
def update_account(
    account_id: int,
    account_update: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Don't allow editing system accounts
    if account.is_system:
        raise HTTPException(status_code=403, detail="Cannot edit system accounts")

    # Check if new account number is already in use (if changed)
    if account_update.account_number != account.account_number:
        existing = db.query(Account).filter(
            Account.account_number == account_update.account_number,
            Account.id != account_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Account number already exists")

    account.account_number = account_update.account_number
    account.account_name = account_update.account_name
    account.account_type = account_update.account_type
    account.parent_account_id = account_update.parent_account_id
    account.description = account_update.description

    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Don't allow deleting system accounts
    if account.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system accounts")

    # Check if account is in use by bank accounts
    bank_account_count = db.query(BankAccount).filter(
        BankAccount.account_id == account_id,
        BankAccount.is_active == True
    ).count()
    if bank_account_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete account. It is used by {bank_account_count} bank account(s)"
        )

    # Check if account has journal entries
    journal_entry_count = db.query(JournalEntry).filter(
        JournalEntry.account_id == account_id
    ).count()
    if journal_entry_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete account. It has {journal_entry_count} journal entries"
        )

    # Soft delete
    account.is_active = False
    db.commit()

    return {"message": "Account deleted successfully"}


@router.post("/{account_id}/toggle-visibility")
def toggle_account_visibility(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Toggle visibility of an account for the current ledger"""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Can only hide/show system accounts
    if not account.is_system:
        raise HTTPException(
            status_code=400,
            detail="Can only toggle visibility for system accounts. Use delete for custom accounts."
        )

    # Check if setting exists
    setting = db.query(LedgerAccountSettings).filter(
        LedgerAccountSettings.ledger_id == current_ledger.id,
        LedgerAccountSettings.account_id == account_id
    ).first()

    if setting:
        # Toggle existing setting
        setting.is_hidden = not setting.is_hidden
        new_state = "hidden" if setting.is_hidden else "visible"
    else:
        # Create new setting (default to hidden)
        setting = LedgerAccountSettings(
            ledger_id=current_ledger.id,
            account_id=account_id,
            is_hidden=True
        )
        db.add(setting)
        new_state = "hidden"

    db.commit()

    return {
        "message": f"Account is now {new_state}",
        "is_hidden": setting.is_hidden
    }
