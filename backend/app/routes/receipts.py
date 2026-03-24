from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
import base64
import json
from pathlib import Path

from backend.database import get_db
from ..models import Receipt, User, Ledger, Transaction, ReceiptStatus, AttachmentType, UserSubscription, SubscriptionPlan, SubscriptionTier, UserMonthlyUsage, SubscriptionStatus
from ..schemas import Receipt as ReceiptSchema, ReceiptCreate
from ..auth import get_current_active_user, get_current_ledger, get_user_from_query_token, get_ledger_from_query
from backend.config import get_settings

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


def check_ai_access(user: User, db: Session):
    """Check if user has Premium subscription required for AI features"""
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.status == SubscriptionStatus.ACTIVE
    ).first()

    if not subscription or subscription.plan.tier != SubscriptionTier.PREMIUM:
        raise HTTPException(
            status_code=403,
            detail="AI-gjenkjenning krever Premium-abonnement."
        )


def increment_ai_usage(user: User, db: Session):
    now = datetime.utcnow()
    usage = db.query(UserMonthlyUsage).filter(
        UserMonthlyUsage.user_id == user.id,
        UserMonthlyUsage.year == now.year,
        UserMonthlyUsage.month == now.month
    ).first()

    if usage:
        usage.ai_operations_count = (usage.ai_operations_count or 0) + 1
    else:
        usage = UserMonthlyUsage(
            user_id=user.id,
            year=now.year,
            month=now.month,
            upload_count=0,
            ai_operations_count=1
        )
        db.add(usage)
    db.commit()


@router.post("/upload", response_model=ReceiptSchema)
async def upload_receipt(
    file: UploadFile = File(...),
    attachment_type: str = Form("RECEIPT"),
    receipt_date: Optional[date] = Form(None),
    due_date: Optional[date] = Form(None),
    amount: Optional[Decimal] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Upload a receipt or invoice"""
    check_subscription_limits(current_user, current_ledger, db)

    try:
        att_type = AttachmentType(attachment_type.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldig vedleggstype. Bruk RECEIPT eller INVOICE.")

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
        attachment_type=att_type,
        receipt_date=receipt_date,
        due_date=due_date,
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

    try:
        receipt.attachment_type = AttachmentType(receipt_update.attachment_type.upper())
    except ValueError:
        pass

    receipt.receipt_date = receipt_update.receipt_date
    receipt.due_date = receipt_update.due_date
    receipt.amount = receipt_update.amount
    receipt.description = receipt_update.description

    db.commit()
    db.refresh(receipt)

    return receipt


@router.post("/{receipt_id}/extract", response_model=ReceiptSchema)
async def extract_receipt_ai(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    settings=Depends(get_settings)
):
    """Extract metadata from receipt/invoice using AI (Premium only)"""
    check_ai_access(current_user, db)

    receipt = db.query(Receipt).filter(
        Receipt.id == receipt_id,
        Receipt.ledger_id == current_ledger.id
    ).options(__import__('sqlalchemy.orm', fromlist=['undefer']).undefer(Receipt.file_data)).first()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if not receipt.file_data:
        raise HTTPException(status_code=400, detail="Ingen bildefil funnet.")

    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="AI-gjenkjenning er ikke konfigurert.")

    # Only images are supported by Anthropic vision API
    supported_types = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}
    mime = (receipt.mime_type or "").lower()
    if mime not in supported_types:
        raise HTTPException(
            status_code=400,
            detail="AI-gjenkjenning støttes kun for bilder (JPEG, PNG, WebP). PDF-filer må registreres manuelt."
        )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        image_data = base64.standard_b64encode(receipt.file_data).decode("utf-8")

        prompt = (
            "Analyser dette vedlegget og ekstraher følgende informasjon som JSON:\n"
            "- vendor: leverandørens navn (string eller null)\n"
            "- date: dato for kvittering/faktura i ISO-format YYYY-MM-DD (string eller null)\n"
            "- amount: totalbeløp inkl. mva som tall uten valutasymbol (number eller null)\n"
            "- due_date: forfallsdato i ISO-format YYYY-MM-DD, kun hvis dette er en faktura (string eller null)\n"
            "- is_invoice: true hvis dette er en faktura med forfallsdato, false hvis kvittering (boolean)\n"
            "- suggested_account: foreslått 4-sifret kontonummer fra norsk kontoplan (string eller null)\n"
            "- confidence: din sikkerhetsscore for ekstraksjonen, 0.0 til 1.0 (number)\n"
            "Svar kun med JSON, ingen forklaringstekst."
        )

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": prompt}
                ],
            }]
        )

        result = json.loads(message.content[0].text)

        receipt.ai_extracted_vendor = result.get("vendor")
        receipt.ai_extracted_description = result.get("vendor")  # vendor as description fallback
        receipt.ai_suggested_account = result.get("suggested_account")
        receipt.ai_confidence = result.get("confidence")
        receipt.ai_processed_at = datetime.utcnow()
        receipt.ai_processing_error = None

        if result.get("amount") is not None:
            receipt.ai_extracted_amount = Decimal(str(result["amount"]))
            if not receipt.amount:
                receipt.amount = receipt.ai_extracted_amount

        if result.get("date"):
            try:
                receipt.ai_extracted_date = date.fromisoformat(result["date"])
                if not receipt.receipt_date:
                    receipt.receipt_date = receipt.ai_extracted_date
            except ValueError:
                pass

        if result.get("due_date"):
            try:
                extracted_due = date.fromisoformat(result["due_date"])
                if not receipt.due_date:
                    receipt.due_date = extracted_due
            except ValueError:
                pass

        if result.get("is_invoice") and not receipt.due_date:
            receipt.attachment_type = AttachmentType.INVOICE

        db.commit()
        db.refresh(receipt)
        increment_ai_usage(current_user, db)

        return receipt

    except json.JSONDecodeError:
        receipt.ai_processing_error = "Kunne ikke tolke AI-svar som JSON"
        db.commit()
        raise HTTPException(status_code=500, detail="AI returnerte ugyldig data. Prøv igjen.")
    except Exception as e:
        receipt.ai_processing_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"AI-gjenkjenning feilet: {str(e)}")


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
