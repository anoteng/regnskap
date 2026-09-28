"""Subscription tier checks shared across routes."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import SubscriptionStatus, SubscriptionTier, User, UserSubscription


def active_tier(user: User, db: Session) -> SubscriptionTier:
    """The user's active tier. No active subscription means FREE."""
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.status == SubscriptionStatus.ACTIVE
    ).first()
    return subscription.plan.tier if subscription else SubscriptionTier.FREE


def require_bank_integration(user: User, db: Session) -> None:
    """Connecting a bank is Premium-only, as advertised in subscription_plans.

    Only the endpoints that start or re-enable a connection are gated —
    syncing and reading existing connections stay open so a downgrade never
    silently breaks data that is already flowing.
    """
    if active_tier(user, db) != SubscriptionTier.PREMIUM:
        raise HTTPException(
            status_code=403,
            detail=(
                "Banktilkobling krever Premium-abonnement. "
                "Du kan importere transaksjoner fra CSV-fil i stedet."
            )
        )
