from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
import uuid
from pathlib import Path

from backend.database import get_db
from ..models import Receipt, User, Ledger, Transaction, ReceiptStatus, UserSubscription, SubscriptionPlan, SubscriptionTier, UserMonthlyUsage, SubscriptionStatus
from ..schemas import Receipt as ReceiptSchema, ReceiptCreate
from ..auth import get_current_active_user, get_current_ledger, get_user_from_query_token, get_ledger_from_query

router = APIRouter(prefix="/receipts", tags=["receipts"])

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.pdf', '.heic'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def check_subscription_limits(user: User, ledger: Ledger, db: Session):
    """Check if user can upload based on subscription limits"""
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.status == SubscriptionStatus.ACTIVE
    ).first()

    if not subscription or subscription.plan.tier == SubscriptionTier.FREE:
        raise HTTPException(
            status_code=403,
            detail="Vedleggsfunksjonen krever Basic-abonnement eller høyere. Oppgrader for 10 kr/mnd."
        )

    plan = subscription.plan

    if plan.max_documents is not None:
        document_count = db.query(func.count(Receipt.id)).filter(
            Receipt.ledger_id == ledger.id
        ).scalar()

        if document_count >= plan.max_documents:
            raise HTTPException(
                status_code=403,
                detail=f"Du har nådd maksgrensen på {plan.max_documents} bilag for {plan.name}-abonnementet. Oppgrader for å laste opp flere."
            )

    if plan.max_monthly_uploads is not None:
        now = datetime.utcnow()
        usage = db.query(UserMonthlyUsage).filter(
            UserMonthlyUsage.user_id == user.id,
            UserMonthlyUsage.year == now.year,
            UserMonthlyUsage.month == now.month
        ).first()

        if usage and usage.upload_count >= plan.max_monthly_uploads:
            raise HTTPException(
                status_code=403,
                detail=f"Du har nådd månedens grense på {plan.max_monthly_uploads} opplastinger for {plan.name}-abonnementet. Oppgrader for ubegrenset opplasting."
            )


def increment_monthly_usage(user: User, db: Session):
    """Increment user's monthly upload count"""
    now = datetime.utcnow()

    usage = db.query(UserMonthlyUsage).filter(
        UserMonthlyUsage.user_id == user.id,
        UserMonthlyUsage.year == now.year,
        UserMonthlyUsage.month == now.month
    ).first()

    if usage:
        usage.upload_count += 1
    else:
        usage = UserMonthlyUsage(
            user_id=user.id,
            year=now.year,
            month=now.month,
            upload_count=1
        )
        db.add(usage)

    db.commit()


@router.post("/upload", response_model=ReceiptSchema)
async def upload_receipt(
    file: UploadFile = File(...),
    receipt_date: Optional[date] = Form(None),
    amount: Optional[Decimal] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Upload a receipt image"""
    check_subscription_limits(current_user, current_ledger, db)

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    contents = await file.read()
    file_size = len(contents)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
        )

    receipt = Receipt(
        ledger_id=current_ledger.id,
        uploaded_by=current_user.id,
        file_data=contents,
        original_filename=file.filename,
        file_size=file_size,
        mime_type=file.content_type,
        receipt_date=receipt_date,
        amount=amount,
        description=description,
        status=ReceiptStatus.PENDING
    )

    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    increment_monthly_usage(current_user, db)

    return receipt


@router.get("/", response_model=List[ReceiptSchema])
def get_receipts(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Get all receipts in queue"""
    query = db.query(Receipt).filter(Receipt.ledger_id == current_ledger.id)

    if status:
        try:
            receipt_status = ReceiptStatus(status)
            query = query.filter(Receipt.status == receipt_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status value")

    receipts = query.order_by(Receipt.created_at.desc()).offset(skip).limit(limit).all()
    return receipts


@router.get("/{receipt_id}", response_model=ReceiptSchema)
def get_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Get a specific receipt"""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id,
        Receipt.ledger_id == current_ledger.id
    ).first()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return receipt


@router.get("/{receipt_id}/image")
def get_receipt_image(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_query_token),
    current_ledger: Ledger = Depends(get_ledger_from_query)
):
    """Get the receipt image file (auth via query params for <img> tags)"""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id,
        Receipt.ledger_id == current_ledger.id
    ).first()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if not receipt.file_data:
        raise HTTPException(status_code=404, detail="Image data not found")

    return Response(
        content=receipt.file_data,
        media_type=receipt.mime_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600"}
    )


@router.post("/{receipt_id}/match/{transaction_id}")
def match_receipt_to_transaction(
    receipt_id: int,
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Match a receipt to a transaction"""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id,
        Receipt.ledger_id == current_ledger.id
    ).first()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.ledger_id == current_ledger.id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    receipt.matched_transaction_id = transaction_id
    receipt.status = ReceiptStatus.MATCHED
    receipt.matched_at = datetime.now()
    receipt.matched_by = current_user.id

    db.commit()
    db.refresh(receipt)

    return {
        "message": "Receipt matched to transaction",
        "receipt_id": receipt_id,
        "transaction_id": transaction_id
    }


@router.post("/{receipt_id}/unmatch")
def unmatch_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Remove match from receipt"""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id,
        Receipt.ledger_id == current_ledger.id
    ).first()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    receipt.matched_transaction_id = None
    receipt.status = ReceiptStatus.PENDING
    receipt.matched_at = None
    receipt.matched_by = None

    db.commit()
    db.refresh(receipt)

    return {"message": "Receipt unmatched"}


@router.delete("/{receipt_id}")
def delete_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Delete a receipt"""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id,
        Receipt.ledger_id == current_ledger.id
    ).first()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    db.delete(receipt)
    db.commit()

    return {"message": "Receipt deleted"}


@router.put("/{receipt_id}", response_model=ReceiptSchema)
def update_receipt(
    receipt_id: int,
    receipt_update: ReceiptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Update receipt metadata"""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id,
        Receipt.ledger_id == current_ledger.id
    ).first()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    receipt.receipt_date = receipt_update.receipt_date
    receipt.amount = receipt_update.amount
    receipt.description = receipt_update.description

    db.commit()
    db.refresh(receipt)

    return receipt


@router.post("/{receipt_id}/rotate")
async def rotate_receipt(
    receipt_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Replace receipt image with rotated version"""
    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id,
        Receipt.ledger_id == current_ledger.id
    ).first()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    contents = await file.read()
    file_size = len(contents)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
        )

    receipt.file_data = contents
    receipt.file_size = file_size
    receipt.mime_type = file.content_type or 'image/jpeg'

    db.commit()

    return {"message": "Receipt rotated successfully"}
