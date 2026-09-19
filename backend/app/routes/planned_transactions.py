from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from backend.database import get_db
from ..models import (
    Account,
    Ledger,
    PlannedTransaction,
    PlannedTransactionStatus,
    Transaction,
    User,
)
from ..schemas import PlannedTransaction as PlannedTransactionSchema, PlannedTransactionUpdate
from ..auth import get_current_active_user, get_current_ledger
from ..planned_transactions import mark_planned_matched

router = APIRouter(prefix="/planned-transactions", tags=["planned-transactions"])


@router.get("/", response_model=List[PlannedTransactionSchema])
def get_planned_transactions(
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """List planned transactions for the current ledger"""
    query = db.query(PlannedTransaction).filter(
        PlannedTransaction.ledger_id == current_ledger.id
    )

    if status:
        try:
            planned_status = PlannedTransactionStatus(status)
            query = query.filter(PlannedTransaction.status == planned_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Ugyldig status. Bruk OPEN, MATCHED eller CANCELLED.")

    if date_from:
        query = query.filter(PlannedTransaction.expected_date >= date_from)
    if date_to:
        query = query.filter(PlannedTransaction.expected_date <= date_to)

    return query.order_by(PlannedTransaction.expected_date).offset(skip).limit(limit).all()


@router.post("/{planned_id}/cancel", response_model=PlannedTransactionSchema)
def cancel_planned_transaction(
    planned_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Cancel an open planned transaction"""
    planned = db.query(PlannedTransaction).filter(
        PlannedTransaction.id == planned_id,
        PlannedTransaction.ledger_id == current_ledger.id
    ).first()

    if not planned:
        raise HTTPException(status_code=404, detail="Planlagt transaksjon ikke funnet")
    if planned.status == PlannedTransactionStatus.MATCHED:
        raise HTTPException(status_code=400, detail="Kan ikke kansellere en matchet planlagt transaksjon")

    planned.status = PlannedTransactionStatus.CANCELLED
    db.commit()
    db.refresh(planned)
    return planned


@router.post("/{planned_id}/reopen", response_model=PlannedTransactionSchema)
def reopen_planned_transaction(
    planned_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Reopen a cancelled planned transaction"""
    planned = db.query(PlannedTransaction).filter(
        PlannedTransaction.id == planned_id,
        PlannedTransaction.ledger_id == current_ledger.id
    ).first()

    if not planned:
        raise HTTPException(status_code=404, detail="Planlagt transaksjon ikke funnet")
    if planned.status != PlannedTransactionStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Kun kansellerte planlagte transaksjoner kan gjenåpnes")

    planned.status = PlannedTransactionStatus.OPEN
    db.commit()
    db.refresh(planned)
    return planned


@router.post("/{planned_id}/match/{transaction_id}", response_model=PlannedTransactionSchema)
def match_planned_transaction(
    planned_id: int,
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Manually match a planned transaction to a transaction"""
    planned = db.query(PlannedTransaction).filter(
        PlannedTransaction.id == planned_id,
        PlannedTransaction.ledger_id == current_ledger.id
    ).first()

    if not planned:
        raise HTTPException(status_code=404, detail="Planlagt transaksjon ikke funnet")
    if planned.status == PlannedTransactionStatus.MATCHED:
        raise HTTPException(status_code=400, detail="Allerede matchet")

    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.ledger_id == current_ledger.id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaksjon ikke funnet")

    mark_planned_matched(db, planned, transaction, matched_by=current_user.id)
    db.commit()
    db.refresh(planned)
    return planned


@router.patch("/{planned_id}", response_model=PlannedTransactionSchema)
def update_planned_transaction(
    planned_id: int,
    payload: PlannedTransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Update expected account/date/amount/description of a planned transaction.

    Only fields present in the request are changed. The expected account is
    what the settlement calculation uses to decide whether the payment counts
    as a shared expense.
    """
    planned = db.query(PlannedTransaction).filter(
        PlannedTransaction.id == planned_id,
        PlannedTransaction.ledger_id == current_ledger.id
    ).first()

    if not planned:
        raise HTTPException(status_code=404, detail="Planlagt transaksjon ikke funnet")
    if planned.status == PlannedTransactionStatus.MATCHED:
        raise HTTPException(status_code=400, detail="Kan ikke endre en matchet planlagt transaksjon")

    fields = payload.model_dump(exclude_unset=True)

    if "suggested_account_id" in fields and fields["suggested_account_id"] is not None:
        account = db.query(Account).filter(
            Account.id == fields["suggested_account_id"],
            Account.ledger_id == current_ledger.id
        ).first()
        if not account:
            raise HTTPException(status_code=400, detail="Kontoen tilhører ikke regnskapet")
    if "amount" in fields and (fields["amount"] is None or fields["amount"] <= 0):
        raise HTTPException(status_code=400, detail="Beløp må være større enn 0")
    if "description" in fields and not (fields["description"] or "").strip():
        raise HTTPException(status_code=400, detail="Beskrivelse kan ikke være tom")
    if "expected_date" in fields and fields["expected_date"] is None:
        raise HTTPException(status_code=400, detail="Forventet dato må angis")

    for name, value in fields.items():
        setattr(planned, name, value.strip() if name == "description" else value)

    db.commit()
    db.refresh(planned)
    return planned
