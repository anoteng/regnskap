from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
import os
import uuid
from pathlib import Path

from backend.database import get_db
from ..models import Receipt, User, Ledger, Transaction, ReceiptStatus
from ..schemas import Receipt as ReceiptSchema, ReceiptCreate
from ..auth import get_current_active_user, get_current_ledger, get_user_from_query_token, get_ledger_from_query

router = APIRouter(prefix="/receipts", tags=["receipts"])

# Configure upload directory
UPLOAD_DIR = Path("uploads/receipts")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.pdf', '.heic'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


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

    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file and check size
    contents = await file.read()
    file_size = len(contents)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
        )

    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = UPLOAD_DIR / str(current_ledger.id) / unique_filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Save file
    with open(file_path, "wb") as f:
        f.write(contents)

    # Create receipt record
    receipt = Receipt(
        ledger_id=current_ledger.id,
        uploaded_by=current_user.id,
        image_path=str(file_path),
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

    if not os.path.exists(receipt.image_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(receipt.image_path)


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

    # Verify transaction exists and belongs to same ledger
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.ledger_id == current_ledger.id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Update receipt
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

    # Delete file from disk
    if os.path.exists(receipt.image_path):
        os.remove(receipt.image_path)

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

    # Validate file extension
    file_ext = Path(file.filename).suffix.lower() or '.jpg'
    if file_ext not in ALLOWED_EXTENSIONS:
        file_ext = '.jpg'

    # Read file
    contents = await file.read()
    file_size = len(contents)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
        )

    # Delete old file
    if os.path.exists(receipt.image_path):
        os.remove(receipt.image_path)

    # Generate new filename (keep same path)
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = UPLOAD_DIR / str(current_ledger.id) / unique_filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Save new file
    with open(file_path, "wb") as f:
        f.write(contents)

    # Update receipt record
    receipt.image_path = str(file_path)
    receipt.file_size = file_size
    receipt.mime_type = file.content_type or 'image/jpeg'

    db.commit()

    return {"message": "Receipt rotated successfully"}
