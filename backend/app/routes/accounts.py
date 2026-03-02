from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from ..models import Account, User, Ledger, BankAccount, JournalEntry, BudgetLine
from ..schemas import Account as AccountSchema, AccountCreate
from ..auth import get_current_active_user, get_current_ledger

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/", response_model=List[AccountSchema])
def get_accounts(
    skip: int = 0,
    limit: int = 1000,
    account_type: str = None,
    show_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Get all accounts for the current ledger."""
    query = db.query(Account).filter(Account.ledger_id == current_ledger.id)

    # Filter by account type if specified
    if account_type:
        query = query.filter(Account.account_type == account_type.upper())

    # Filter out inactive accounts unless explicitly requested
    if not show_inactive:
        query = query.filter(Account.is_active == True)

    # Sort by account number
    query = query.order_by(Account.account_number)

    accounts = query.offset(skip).limit(limit).all()
    return accounts


@router.post("/", response_model=AccountSchema)
def create_account(
    account: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Create a new account in the current ledger."""
    # Check if account number already exists in this ledger
    existing = db.query(Account).filter(
        Account.ledger_id == current_ledger.id,
        Account.account_number == account.account_number
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Account number already exists in this ledger"
        )

    db_account = Account(
        ledger_id=current_ledger.id,
        account_number=account.account_number,
        account_name=account.account_name,
        account_type=account.account_type,
        parent_account_id=account.parent_account_id,
        description=account.description,
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
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Get a specific account."""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.ledger_id == current_ledger.id
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return account


@router.put("/{account_id}", response_model=AccountSchema)
def update_account(
    account_id: int,
    account_update: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Update an account."""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.ledger_id == current_ledger.id
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Check if new account number is already in use (if changed)
    if account_update.account_number != account.account_number:
        existing = db.query(Account).filter(
            Account.ledger_id == current_ledger.id,
            Account.account_number == account_update.account_number,
            Account.id != account_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Account number already exists in this ledger"
            )

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
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Delete (soft delete) an account."""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.ledger_id == current_ledger.id
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Check if account is in use by bank accounts
    bank_account_count = db.query(BankAccount).filter(
        BankAccount.account_id == account_id,
        BankAccount.is_active == True
    ).count()
    if bank_account_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Kan ikke slette kontoen. Den brukes av {bank_account_count} bankkonto(er)"
        )

    # Check if account has journal entries
    journal_entry_count = db.query(JournalEntry).filter(
        JournalEntry.account_id == account_id
    ).count()
    if journal_entry_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Kan ikke slette kontoen. Den har {journal_entry_count} posteringer"
        )

    # Check if account is used in budgets
    budget_line_count = db.query(BudgetLine).filter(
        BudgetLine.account_id == account_id
    ).count()
    if budget_line_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Kan ikke slette kontoen. Den brukes i {budget_line_count} budsjettlinje(r)"
        )

    # Soft delete
    account.is_active = False
    db.commit()

    return {"message": "Account deleted successfully"}


@router.post("/{account_id}/toggle-active")
def toggle_account_active(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Toggle active status of an account."""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.ledger_id == current_ledger.id
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Toggle active status
    account.is_active = not account.is_active
    new_state = "active" if account.is_active else "inactive"

    db.commit()

    return {
        "message": f"Account is now {new_state}",
        "is_active": account.is_active
    }
