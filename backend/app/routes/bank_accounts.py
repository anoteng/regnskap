from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from decimal import Decimal

from backend.database import get_db
from ..models import BankAccount, User, Ledger, Transaction, JournalEntry, Account
from ..schemas import BankAccount as BankAccountSchema, BankAccountCreate, BankAccountUpdate
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

    If opening_balance is provided, creates an IB (Ingående Balans) transaction
    dated 2026-01-01 with:
    - Debit: Bank account
    - Credit: IB account (2050)
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
        # Find IB account (2050 - Inngående balanse)
        ib_account = db.query(Account).filter(
            Account.ledger_id == current_ledger.id,
            Account.account_number == "2050"
        ).first()

        if not ib_account:
            raise HTTPException(
                status_code=404,
                detail="IB-konto (2050) ikke funnet. Opprett kontoen først."
            )

        # Check if IB transaction already exists for this bank account
        existing_ib = db.query(Transaction).join(JournalEntry).filter(
            Transaction.ledger_id == current_ledger.id,
            Transaction.description.like(f"%Ingående balans%{bank_account.name}%"),
            JournalEntry.account_id == bank_account.account_id
        ).first()

        if existing_ib and existing_ib.status == "POSTED":
            raise HTTPException(
                status_code=400,
                detail="Ingående balans allerede registrert. Slett eksisterende transaksjon først."
            )

        # Create IB transaction
        ib_transaction = Transaction(
            ledger_id=current_ledger.id,
            description=f"Ingående balans - {bank_account.name}",
            transaction_date=datetime(2026, 1, 1).date(),
            created_by=current_user.id,
            status="POSTED",  # IB transactions are posted immediately
            source="MANUAL",
            is_reconciled=False
        )
        db.add(ib_transaction)
        db.flush()  # Get transaction ID

        # Create journal entries
        # Debit: Bank account
        debit_entry = JournalEntry(
            transaction_id=ib_transaction.id,
            account_id=bank_account.account_id,
            debit=abs(updates.opening_balance),
            credit=Decimal("0.00"),
            description=f"IB {bank_account.name}"
        )

        # Credit: IB account (2050)
        credit_entry = JournalEntry(
            transaction_id=ib_transaction.id,
            account_id=ib_account.id,
            debit=Decimal("0.00"),
            credit=abs(updates.opening_balance),
            description=f"IB {bank_account.name}"
        )

        db.add(debit_entry)
        db.add(credit_entry)

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
