from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import secrets

from backend.database import get_db
from backend.config import get_settings
from backend.email import send_password_reset_email
from ..models import User, PasswordResetToken, WebAuthnCredential, UserSubscription, SubscriptionStatus, Ledger, LedgerMember, LedgerRole
from ..schemas import Token, RefreshRequest, UserCreate, User as UserSchema, PasswordResetRequest, PasswordResetComplete, PasswordResetResponse
from ..auth import authenticate_user, create_access_token, create_refresh_token, verify_refresh_token, revoke_refresh_token, get_password_hash, get_current_active_user

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
    refresh_token = create_refresh_token(db, user.id)
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}


@router.post("/refresh", response_model=Token)
def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    """Issue new access token using a valid refresh token."""
    user = verify_refresh_token(db, request.refresh_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ugyldig eller utløpt refresh token"
        )
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": request.refresh_token}


@router.post("/biometric-token")
async def create_biometric_token(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a dedicated refresh token for biometric login. Not revoked on regular logout."""
    refresh_token = create_refresh_token(db, current_user.id)
    return {"refresh_token": refresh_token}


@router.post("/logout")
def logout(request: RefreshRequest, db: Session = Depends(get_db)):
    """Invalidate refresh token."""
    revoke_refresh_token(db, request.refresh_token)
    return {"message": "Logget ut"}


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


@router.get("/me", response_model=UserSchema)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Get current authenticated user information"""
    return current_user


@router.get("/me/subscription")
async def get_my_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's subscription info"""
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == SubscriptionStatus.ACTIVE
    ).first()

    if not subscription:
        return {"tier": "FREE", "plan_name": "Gratis", "has_subscription": False}

    plan = subscription.plan
    return {
        "tier": plan.tier.value,
        "plan_name": plan.name,
        "has_subscription": True,
        "price_monthly": float(plan.price_monthly),
        "price_yearly": float(plan.price_yearly) if plan.price_yearly else None,
        "features": plan.features,
    }


@router.delete("/me")
async def delete_my_account(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Permanently delete the current user's account.

    For each ledger where the user is the sole owner, the ledger is soft-deleted.
    For ledgers with other owners, the user is simply removed as a member.
    The user account is then deactivated and anonymised.
    """
    memberships = db.query(LedgerMember).filter(
        LedgerMember.user_id == current_user.id
    ).all()

    for membership in memberships:
        if membership.role == LedgerRole.OWNER:
            other_owners = db.query(LedgerMember).filter(
                LedgerMember.ledger_id == membership.ledger_id,
                LedgerMember.user_id != current_user.id,
                LedgerMember.role == LedgerRole.OWNER
            ).count()

            if other_owners == 0:
                # Sole owner — soft-delete the ledger
                ledger = db.query(Ledger).filter(Ledger.id == membership.ledger_id).first()
                if ledger:
                    ledger.is_active = False

        db.delete(membership)

    # Anonymise and deactivate the account
    current_user.is_active = False
    current_user.full_name = "Slettet bruker"
    current_user.email = f"deleted_{current_user.id}@deleted.invalid"

    db.commit()
    return {"message": "Konto slettet"}
