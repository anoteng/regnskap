from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from decimal import Decimal
from pydantic import BaseModel

from backend.database import get_db
from backend.app import models
from backend.app.auth import get_current_active_user, get_current_ledger
from backend.app.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


class AnalyzeReceiptResponse(BaseModel):
    success: bool
    extracted_data: Optional[dict] = None
    error: Optional[str] = None


class PostingSuggestionRequest(BaseModel):
    description: str
    amount: float
    transaction_date: date
    vendor: Optional[str] = None


class PostingSuggestionResponse(BaseModel):
    success: bool
    suggestion: Optional[dict] = None
    error: Optional[str] = None


@router.post("/analyze-receipt/{receipt_id}", response_model=AnalyzeReceiptResponse)
async def analyze_receipt(
    receipt_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    current_ledger: models.Ledger = Depends(get_current_ledger)
):
    """
    Analyze a receipt using AI to extract structured data
    """
    # Get receipt
    receipt = db.query(models.Receipt).filter(
        models.Receipt.id == receipt_id,
        models.Receipt.ledger_id == current_ledger.id
    ).first()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    try:
        # Initialize AI service
        ai_service = AIService(db)

        # Analyze receipt
        extracted_data = await ai_service.analyze_receipt(receipt, current_user, current_ledger)

        # Update receipt with AI-extracted data
        receipt.ai_extracted_date = extracted_data.get('date')
        receipt.ai_extracted_amount = Decimal(str(extracted_data.get('amount'))) if extracted_data.get('amount') else None
        receipt.ai_extracted_vendor = extracted_data.get('vendor')
        receipt.ai_extracted_description = extracted_data.get('description')
        receipt.ai_suggested_account = extracted_data.get('suggested_account')
        receipt.ai_confidence = Decimal(str(extracted_data.get('confidence', 0)))
        receipt.ai_processed_at = db.func.now()

        # If user hasn't manually set fields, use AI suggestions
        if not receipt.receipt_date and receipt.ai_extracted_date:
            receipt.receipt_date = receipt.ai_extracted_date
        if not receipt.amount and receipt.ai_extracted_amount:
            receipt.amount = receipt.ai_extracted_amount
        if not receipt.description and receipt.ai_extracted_description:
            receipt.description = receipt.ai_extracted_description

        db.commit()
        db.refresh(receipt)

        return AnalyzeReceiptResponse(
            success=True,
            extracted_data=extracted_data
        )

    except Exception as e:
        # Log error to receipt
        receipt.ai_processing_error = str(e)
        db.commit()

        return AnalyzeReceiptResponse(
            success=False,
            error=str(e)
        )


@router.post("/suggest-posting", response_model=PostingSuggestionResponse)
async def suggest_posting(
    data: PostingSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    current_ledger: models.Ledger = Depends(get_current_ledger)
):
    """
    Get AI suggestion for journal entries based on transaction details
    """
    try:
        ai_service = AIService(db)

        suggestion = await ai_service.suggest_posting(
            description=data.description,
            amount=Decimal(str(data.amount)),
            transaction_date=data.transaction_date,
            user=current_user,
            ledger=current_ledger,
            vendor=data.vendor
        )

        return PostingSuggestionResponse(
            success=True,
            suggestion=suggestion
        )

    except Exception as e:
        return PostingSuggestionResponse(
            success=False,
            error=str(e)
        )


@router.get("/my-usage")
async def get_my_ai_usage(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Get current user's AI usage statistics
    """
    ai_service = AIService(db)
    stats = ai_service.get_user_usage_stats(current_user.id)

    return stats
