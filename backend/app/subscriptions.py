"""Subscription tier checks shared across routes."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .bank_integration.encryption import TokenEncryption
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


def personal_ai_key(user: User) -> Optional[str]:
    """The user's own Anthropic key, or None if they haven't set one."""
    if not user.ai_api_key_encrypted:
        return None
    try:
        return TokenEncryption().decrypt(user.ai_api_key_encrypted)
    except Exception:
        # A key encrypted under a rotated SECRET_KEY is unusable; treat as unset
        return None


def resolve_ai_api_key(user: User, db: Session, platform_key: Optional[str]) -> str:
    """Which Anthropic key AI features should run on.

    A personal key always wins: it costs the platform nothing, so it unlocks AI
    on any tier. Without one, AI is a Premium feature on the platform key.
    """
    own = personal_ai_key(user)
    if own:
        return own

    if active_tier(user, db) != SubscriptionTier.PREMIUM:
        raise HTTPException(
            status_code=403,
            detail=(
                "AI-gjenkjenning krever Premium-abonnement, eller at du legger inn "
                "din egen API-nøkkel under innstillinger."
            )
        )

    if not platform_key:
        raise HTTPException(status_code=503, detail="AI-gjenkjenning er ikke konfigurert.")
    return platform_key
