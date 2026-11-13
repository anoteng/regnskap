"""Personal API keys: made, listed and revoked by the logged-in user."""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from ..auth import get_current_active_user
from ..models import ApiToken, Ledger, LedgerMember, User

router = APIRouter(prefix="/api-tokens", tags=["api-tokens"])

TOKEN_PREFIX = "pr_"


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    # None reads every ledger the user is a member of
    ledger_id: Optional[int] = None
    # Writing is also bounded by the user's role in each ledger
    can_write: bool = False
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650)


class ApiTokenOut(BaseModel):
    id: int
    name: str
    ledger_id: Optional[int]
    ledger_name: Optional[str]
    can_write: bool
    token_prefix: str
    created_at: Optional[datetime]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]


class ApiTokenCreated(ApiTokenOut):
    # Shown this once and never again
    token: str


def _out(token: ApiToken) -> dict:
    return {
        "id": token.id,
        "name": token.name,
        "ledger_id": token.ledger_id,
        "ledger_name": token.ledger.name if token.ledger else None,
        "can_write": bool(token.can_write),
        "token_prefix": token.token_prefix,
        "created_at": token.created_at,
        "expires_at": token.expires_at,
        "last_used_at": token.last_used_at,
    }


@router.get("/", response_model=List[ApiTokenOut])
def list_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tokens = db.query(ApiToken).filter(
        ApiToken.user_id == current_user.id,
        ApiToken.revoked_at.is_(None),
    ).order_by(ApiToken.created_at.desc()).all()
    return [_out(t) for t in tokens]


@router.post("/", response_model=ApiTokenCreated)
def create_token(
    payload: ApiTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.ledger_id is not None:
        member = db.query(LedgerMember).join(Ledger).filter(
            LedgerMember.ledger_id == payload.ledger_id,
            LedgerMember.user_id == current_user.id,
            Ledger.is_active == True,
        ).first()
        if not member:
            raise HTTPException(status_code=404, detail="Fant ikke regnskapet")

    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    token = ApiToken(
        user_id=current_user.id,
        ledger_id=payload.ledger_id,
        can_write=payload.can_write,
        name=payload.name.strip(),
        token_prefix=raw[:10],
        token_hash=hash_token(raw),
        expires_at=(datetime.utcnow() + timedelta(days=payload.expires_in_days))
        if payload.expires_in_days else None,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return {**_out(token), "token": raw}


@router.delete("/{token_id}")
def revoke_token(
    token_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    token = db.query(ApiToken).filter(
        ApiToken.id == token_id,
        ApiToken.user_id == current_user.id,
        ApiToken.revoked_at.is_(None),
    ).first()
    if not token:
        raise HTTPException(status_code=404, detail="Fant ikke nøkkelen")
    # Kept, not deleted: last_used_at says whether it was in use
    token.revoked_at = datetime.utcnow()
    db.commit()
    return {"message": "Nøkkelen er tilbakekalt"}
