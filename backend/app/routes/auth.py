from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import secrets

from backend.database import get_db
from backend.config import get_settings
from backend.email import send_password_reset_email
from ..models import User, PasswordResetToken, WebAuthnCredential
from ..schemas import Token, UserCreate, User as UserSchema, PasswordResetRequest, PasswordResetComplete, PasswordResetResponse
from ..auth import authenticate_user, create_access_token, get_password_hash

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=UserSchema)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/password-reset/request", response_model=PasswordResetResponse)
def request_password_reset(request: PasswordResetRequest, db: Session = Depends(get_db)):
    """Request password reset - sends email if user exists"""

    user = db.query(User).filter(User.email == request.email).first()

    # Always return success to prevent email enumeration
    if not user:
        return {
            "message": "Hvis e-postadressen er registrert, vil du motta en e-post med instruksjoner.",
            "has_passkey": False
        }

    # Check if user has passkey
    has_passkey = db.query(WebAuthnCredential).filter(
        WebAuthnCredential.user_id == user.id
    ).first() is not None

    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    # Delete any existing unused tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None)
    ).delete()

    # Create new token
    db_token = PasswordResetToken(
        user_id=user.id,
        token=reset_token,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()

    # Send email
    try:
        send_password_reset_email(user.email, reset_token, user.full_name)
    except Exception as e:
        # Log error but don't expose it to user
        print(f"Failed to send password reset email: {e}")

    return {
        "message": "Hvis e-postadressen er registrert, vil du motta en e-post med instruksjoner.",
        "has_passkey": has_passkey
    }


@router.post("/password-reset/complete")
def complete_password_reset(request: PasswordResetComplete, db: Session = Depends(get_db)):
    """Complete password reset with token from email"""

    # Find valid token
    db_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == request.token,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ugyldig eller utløpt tilbakestillings-token"
        )

    # Update user password
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Bruker ikke funnet")

    user.hashed_password = get_password_hash(request.new_password)

    # Mark token as used
    db_token.used_at = datetime.utcnow()

    db.commit()

    return {"message": "Passord tilbakestilt!"}
