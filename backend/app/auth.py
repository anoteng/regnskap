from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Header, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from .models import User, Ledger, LedgerMember, LedgerRole
from .schemas import TokenData

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_ledger(
    ledger_id: Optional[int] = Header(None, alias="X-Ledger-ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Ledger:
    """
    Get current ledger from header or user's last_active_ledger_id.
    Verify user has access to the ledger.
    """
    # If no ledger_id in header, use user's last active
    if ledger_id is None:
        ledger_id = current_user.last_active_ledger_id

    # If still no ledger, user needs to create one
    if ledger_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ledger selected. Please create or select a ledger."
        )

    # Get the ledger
    ledger = db.query(Ledger).filter(Ledger.id == ledger_id, Ledger.is_active == True).first()
    if not ledger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ledger not found"
        )

    # Verify user is a member of this ledger
    membership = db.query(LedgerMember).filter(
        LedgerMember.ledger_id == ledger_id,
        LedgerMember.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ledger"
        )

    return ledger


def get_user_role_in_ledger(db: Session, user_id: int, ledger_id: int) -> Optional[LedgerRole]:
    """Get user's role in a specific ledger."""
    membership = db.query(LedgerMember).filter(
        LedgerMember.ledger_id == ledger_id,
        LedgerMember.user_id == user_id
    ).first()

    return membership.role if membership else None


def user_can_write(db: Session, user_id: int, ledger_id: int) -> bool:
    """Check if user can create/edit in ledger (OWNER or MEMBER)."""
    role = get_user_role_in_ledger(db, user_id, ledger_id)
    return role in [LedgerRole.OWNER, LedgerRole.MEMBER]


def user_can_read(db: Session, user_id: int, ledger_id: int) -> bool:
    """Check if user can view ledger (any role)."""
    role = get_user_role_in_ledger(db, user_id, ledger_id)
    return role is not None


def require_ledger_owner(
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    db: Session = Depends(get_db)
):
    """Verify user is OWNER of current ledger."""
    role = get_user_role_in_ledger(db, current_user.id, current_ledger.id)
    if role != LedgerRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ledger owners can perform this action"
        )
    return current_ledger


def require_ledger_write(
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    db: Session = Depends(get_db)
):
    """Verify user can write to current ledger (OWNER or MEMBER)."""
    if not user_can_write(db, current_user.id, current_ledger.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this ledger"
        )
    return current_ledger


async def get_user_from_query_token(
    token: str = Query(...),
    db: Session = Depends(get_db)
) -> User:
    """Get user from token passed as query parameter (for image URLs)"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_ledger_from_query(
    ledger: int = Query(...),
    current_user: User = Depends(get_user_from_query_token),
    db: Session = Depends(get_db)
) -> Ledger:
    """Get ledger from query parameter, verify user has access"""
    ledger_obj = db.query(Ledger).filter(Ledger.id == ledger).first()
    if not ledger_obj:
        raise HTTPException(status_code=404, detail="Ledger not found")

    # Verify user has access
    membership = db.query(LedgerMember).filter(
        LedgerMember.ledger_id == ledger,
        LedgerMember.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ledger"
        )

    return ledger_obj
