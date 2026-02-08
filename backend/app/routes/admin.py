from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from datetime import datetime, timedelta, date
from backend.database import get_db
from backend.app import models, schemas
from backend.app.auth import get_current_user, get_password_hash
from pydantic import BaseModel, EmailStr
from decimal import Decimal

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
    features: Optional[str]
    max_documents: Optional[int]
    max_monthly_uploads: Optional[int]
    ai_enabled: bool
    max_ai_operations_per_month: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True


class UpdateSubscriptionPlanRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[float] = None
    features: Optional[str] = None
    max_documents: Optional[int] = None
    max_monthly_uploads: Optional[int] = None
    ai_enabled: Optional[bool] = None
    max_ai_operations_per_month: Optional[int] = None
    is_active: Optional[bool] = None


class AIConfigInfo(BaseModel):
    id: int
    provider: str
    model: str
    is_active: bool
    max_tokens: int
    temperature: float
    config_notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateAIConfigRequest(BaseModel):
    provider: str
    api_key: str
    model: str
    max_tokens: Optional[int] = 4000
    temperature: Optional[float] = 0.3
    config_notes: Optional[str] = None


class UpdateAIConfigRequest(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None
    is_active: Optional[bool] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    config_notes: Optional[str] = None


class UserAIUsageStats(BaseModel):
    user_id: int
    user_email: str
    user_name: str
    total_operations: int
    total_tokens: int
    total_cost_usd: float
    last_used: Optional[datetime]


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
            features=plan.features,
            max_documents=plan.max_documents,
            max_monthly_uploads=plan.max_monthly_uploads,
            ai_enabled=plan.ai_enabled,
            max_ai_operations_per_month=plan.max_ai_operations_per_month,
            is_active=plan.is_active
        )
        for plan in plans
    ]


@router.patch("/subscription-plans/{plan_id}")
def update_subscription_plan(
    plan_id: int,
    data: UpdateSubscriptionPlanRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Update subscription plan details"""
    plan = db.query(models.SubscriptionPlan).filter(
        models.SubscriptionPlan.id == plan_id
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    # Update fields if provided
    if data.name is not None:
        plan.name = data.name
    if data.description is not None:
        plan.description = data.description
    if data.price_monthly is not None:
        plan.price_monthly = data.price_monthly
    if data.features is not None:
        plan.features = data.features
    if data.max_documents is not None:
        plan.max_documents = data.max_documents
    if data.max_monthly_uploads is not None:
        plan.max_monthly_uploads = data.max_monthly_uploads
    if data.ai_enabled is not None:
        plan.ai_enabled = data.ai_enabled
    if data.max_ai_operations_per_month is not None:
        plan.max_ai_operations_per_month = data.max_ai_operations_per_month
    if data.is_active is not None:
        plan.is_active = data.is_active

    db.commit()
    db.refresh(plan)

    return {"message": "Subscription plan updated successfully"}


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


# ============================================
# AI CONFIGURATION ENDPOINTS
# ============================================

@router.get("/ai-config", response_model=List[AIConfigInfo])
def list_ai_configs(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """List all AI configurations"""
    configs = db.query(models.AIConfig).all()
    return configs


@router.post("/ai-config")
def create_ai_config(
    data: CreateAIConfigRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Create a new AI configuration"""
    # Deactivate other configs if this is being set as active
    if data.provider:
        db.query(models.AIConfig).update({"is_active": False})

    config = models.AIConfig(
        provider=data.provider,
        api_key=data.api_key,
        model=data.model,
        max_tokens=data.max_tokens,
        temperature=data.temperature,
        config_notes=data.config_notes,
        is_active=True
    )

    db.add(config)
    db.commit()
    db.refresh(config)

    return {"message": "AI configuration created", "id": config.id}


@router.patch("/ai-config/{config_id}")
def update_ai_config(
    config_id: int,
    data: UpdateAIConfigRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Update AI configuration"""
    config = db.query(models.AIConfig).filter(
        models.AIConfig.id == config_id
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="AI config not found")

    # If activating this config, deactivate others
    if data.is_active and not config.is_active:
        db.query(models.AIConfig).update({"is_active": False})

    if data.api_key is not None:
        config.api_key = data.api_key
    if data.model is not None:
        config.model = data.model
    if data.is_active is not None:
        config.is_active = data.is_active
    if data.max_tokens is not None:
        config.max_tokens = data.max_tokens
    if data.temperature is not None:
        config.temperature = data.temperature
    if data.config_notes is not None:
        config.config_notes = data.config_notes

    db.commit()
    db.refresh(config)

    return {"message": "AI configuration updated"}


@router.delete("/ai-config/{config_id}")
def delete_ai_config(
    config_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Delete AI configuration"""
    config = db.query(models.AIConfig).filter(
        models.AIConfig.id == config_id
    ).first()

    if not config:
        raise HTTPException(status_code=404, detail="AI config not found")

    db.delete(config)
    db.commit()

    return {"message": "AI configuration deleted"}


# ============================================
# AI USAGE TRACKING ENDPOINTS
# ============================================

@router.get("/ai-usage/users", response_model=List[UserAIUsageStats])
def get_ai_usage_by_users(
    start_date: Optional[date] = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Get AI usage statistics grouped by user"""
    query = db.query(
        models.AIUsage.user_id,
        models.User.email,
        models.User.full_name,
        func.count(models.AIUsage.id).label('total_operations'),
        func.sum(models.AIUsage.tokens_used).label('total_tokens'),
        func.sum(models.AIUsage.cost_usd).label('total_cost_usd'),
        func.max(models.AIUsage.created_at).label('last_used')
    ).join(models.User).group_by(
        models.AIUsage.user_id,
        models.User.email,
        models.User.full_name
    )

    if start_date:
        query = query.filter(models.AIUsage.created_at >= start_date)

    results = query.all()

    return [
        UserAIUsageStats(
            user_id=r.user_id,
            user_email=r.email,
            user_name=r.full_name,
            total_operations=r.total_operations,
            total_tokens=r.total_tokens or 0,
            total_cost_usd=float(r.total_cost_usd or 0),
            last_used=r.last_used
        )
        for r in results
    ]


@router.get("/ai-usage/user/{user_id}")
def get_user_ai_usage(
    user_id: int,
    start_date: Optional[date] = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    """Get detailed AI usage for a specific user"""
    query = db.query(models.AIUsage).filter(
        models.AIUsage.user_id == user_id
    )

    if start_date:
        query = query.filter(models.AIUsage.created_at >= start_date)

    usages = query.order_by(models.AIUsage.created_at.desc()).all()

    total_tokens = sum(u.tokens_used for u in usages)
    total_cost = sum(u.cost_usd or 0 for u in usages)

    by_operation = {}
    for usage in usages:
        if usage.operation_type not in by_operation:
            by_operation[usage.operation_type] = {'count': 0, 'tokens': 0, 'cost': 0}
        by_operation[usage.operation_type]['count'] += 1
        by_operation[usage.operation_type]['tokens'] += usage.tokens_used
        by_operation[usage.operation_type]['cost'] += float(usage.cost_usd or 0)

    return {
        'user_id': user_id,
        'total_operations': len(usages),
        'total_tokens': total_tokens,
        'total_cost_usd': float(total_cost),
        'by_operation': by_operation,
        'recent_usage': [
            {
                'id': u.id,
                'operation_type': u.operation_type,
                'provider': u.provider,
                'model': u.model,
                'tokens_used': u.tokens_used,
                'cost_usd': float(u.cost_usd or 0),
                'created_at': u.created_at
            }
            for u in usages[:20]  # Last 20 operations
        ]
    }
