from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from datetime import datetime, timedelta
from backend.database import get_db
from backend.app import models, schemas
from backend.app.auth import get_current_user, get_password_hash
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/admin", tags=["admin"])


# Dependency to check if user is admin
def require_admin(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# Schemas
class UserListItem(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    ledger_count: int = 0
    has_subscription: bool = False
    subscription_tier: Optional[str] = None
    subscription_expires: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserDetail(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    last_active_ledger_id: Optional[int]
    ledger_count: int = 0
    subscription: Optional["SubscriptionInfo"] = None

    class Config:
        from_attributes = True


class SubscriptionInfo(BaseModel):
    id: int
    plan_id: int
    plan_name: str
    plan_tier: str
    status: str
    started_at: datetime
    expires_at: Optional[datetime]
    discount_percentage: float
    custom_price: Optional[float]
    is_free_forever: bool
    admin_notes: Optional[str]

    class Config:
        from_attributes = True


class SubscriptionPlanInfo(BaseModel):
    id: int
    name: str
    tier: str
    description: Optional[str]
    price_monthly: float
    is_active: bool

    class Config:
        from_attributes = True


class UpdateUserRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class SetPasswordRequest(BaseModel):
    new_password: str


class UpdateSubscriptionRequest(BaseModel):
    plan_id: int
    expires_at: Optional[datetime] = None
    discount_percentage: Optional[float] = 0
    custom_price: Optional[float] = None
    is_free_forever: Optional[bool] = False
    admin_notes: Optional[str] = None


# ============================================
# USER MANAGEMENT ENDPOINTS
# ============================================

@router.get("/users", response_model=List[UserListItem])
def list_users(
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """List all users with search and filter"""
    query = db.query(models.User)

    # Search filter
    if search:
        query = query.filter(
            or_(
                models.User.email.ilike(f"%{search}%"),
                models.User.full_name.ilike(f"%{search}%")
            )
        )

    # Active filter
    if is_active is not None:
        query = query.filter(models.User.is_active == is_active)

    # Get users
    users = query.offset(skip).limit(limit).all()

    # Enrich with additional data
    result = []
    for user in users:
        # Count ledgers
        ledger_count = db.query(func.count(models.LedgerMember.ledger_id))\
            .filter(models.LedgerMember.user_id == user.id)\
            .scalar()

        # Get subscription
        subscription = db.query(models.UserSubscription)\
            .filter(models.UserSubscription.user_id == user.id)\
            .filter(models.UserSubscription.status == models.SubscriptionStatus.ACTIVE)\
            .first()

        user_data = UserListItem(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            ledger_count=ledger_count,
            has_subscription=subscription is not None,
            subscription_tier=subscription.plan.tier.value if subscription else None,
            subscription_expires=subscription.expires_at if subscription else None
        )
        result.append(user_data)

    return result


@router.get("/users/{user_id}", response_model=UserDetail)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Get detailed user information"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Count ledgers
    ledger_count = db.query(func.count(models.LedgerMember.ledger_id))\
        .filter(models.LedgerMember.user_id == user.id)\
        .scalar()

    # Get subscription
    subscription = db.query(models.UserSubscription)\
        .join(models.SubscriptionPlan)\
        .filter(models.UserSubscription.user_id == user.id)\
        .filter(models.UserSubscription.status == models.SubscriptionStatus.ACTIVE)\
        .first()

    subscription_info = None
    if subscription:
        subscription_info = SubscriptionInfo(
            id=subscription.id,
            plan_id=subscription.plan_id,
            plan_name=subscription.plan.name,
            plan_tier=subscription.plan.tier.value,
            status=subscription.status.value,
            started_at=subscription.started_at,
            expires_at=subscription.expires_at,
            discount_percentage=float(subscription.discount_percentage),
            custom_price=float(subscription.custom_price) if subscription.custom_price else None,
            is_free_forever=subscription.is_free_forever,
            admin_notes=subscription.admin_notes
        )

    return UserDetail(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_active_ledger_id=user.last_active_ledger_id,
        ledger_count=ledger_count,
        subscription=subscription_info
    )


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    data: UpdateUserRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Update user details"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.email is not None:
        # Check if email already exists
        existing = db.query(models.User).filter(
            models.User.email == data.email,
            models.User.id != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = data.email

    if data.full_name is not None:
        user.full_name = data.full_name

    if data.is_active is not None:
        user.is_active = data.is_active

    if data.is_admin is not None:
        user.is_admin = data.is_admin

    db.commit()
    db.refresh(user)

    return {"message": "User updated successfully"}


@router.post("/users/{user_id}/password")
def set_user_password(
    user_id: int,
    data: SetPasswordRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Set password for a user"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = get_password_hash(data.new_password)
    db.commit()

    return {"message": "Password updated successfully"}


# ============================================
# SUBSCRIPTION MANAGEMENT ENDPOINTS
# ============================================

@router.get("/subscription-plans", response_model=List[SubscriptionPlanInfo])
def list_subscription_plans(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """List all subscription plans"""
    plans = db.query(models.SubscriptionPlan).filter(
        models.SubscriptionPlan.is_active == True
    ).all()

    return [
        SubscriptionPlanInfo(
            id=plan.id,
            name=plan.name,
            tier=plan.tier.value,
            description=plan.description,
            price_monthly=float(plan.price_monthly),
            is_active=plan.is_active
        )
        for plan in plans
    ]


@router.post("/users/{user_id}/subscription")
def create_or_update_subscription(
    user_id: int,
    data: UpdateSubscriptionRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Create or update user subscription"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan = db.query(models.SubscriptionPlan).filter(
        models.SubscriptionPlan.id == data.plan_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    # Cancel any existing active subscription
    existing = db.query(models.UserSubscription).filter(
        models.UserSubscription.user_id == user_id,
        models.UserSubscription.status == models.SubscriptionStatus.ACTIVE
    ).first()

    if existing:
        existing.status = models.SubscriptionStatus.CANCELLED
        existing.cancelled_at = datetime.utcnow()

    # Create new subscription
    subscription = models.UserSubscription(
        user_id=user_id,
        plan_id=data.plan_id,
        status=models.SubscriptionStatus.ACTIVE,
        expires_at=data.expires_at,
        discount_percentage=data.discount_percentage or 0,
        custom_price=data.custom_price,
        is_free_forever=data.is_free_forever or False,
        admin_notes=data.admin_notes
    )

    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    return {"message": "Subscription updated successfully", "subscription_id": subscription.id}


@router.delete("/users/{user_id}/subscription")
def cancel_subscription(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Cancel user's active subscription"""
    subscription = db.query(models.UserSubscription).filter(
        models.UserSubscription.user_id == user_id,
        models.UserSubscription.status == models.SubscriptionStatus.ACTIVE
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")

    subscription.status = models.SubscriptionStatus.CANCELLED
    subscription.cancelled_at = datetime.utcnow()

    db.commit()

    return {"message": "Subscription cancelled successfully"}


# ============================================
# STATISTICS ENDPOINTS
# ============================================

@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Get admin dashboard statistics"""
    total_users = db.query(func.count(models.User.id)).scalar()
    active_users = db.query(func.count(models.User.id)).filter(
        models.User.is_active == True
    ).scalar()

    total_ledgers = db.query(func.count(models.Ledger.id)).scalar()
    active_subscriptions = db.query(func.count(models.UserSubscription.id)).filter(
        models.UserSubscription.status == models.SubscriptionStatus.ACTIVE
    ).scalar()

    # Count by subscription tier
    tier_counts = db.query(
        models.SubscriptionPlan.tier,
        func.count(models.UserSubscription.id)
    ).join(models.UserSubscription).filter(
        models.UserSubscription.status == models.SubscriptionStatus.ACTIVE
    ).group_by(models.SubscriptionPlan.tier).all()

    tier_distribution = {tier.value: count for tier, count in tier_counts}

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_ledgers": total_ledgers,
        "active_subscriptions": active_subscriptions,
        "tier_distribution": tier_distribution
    }
