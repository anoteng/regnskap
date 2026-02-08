"""
Bank Integration Admin Routes

Admin endpoints for managing bank providers and monitoring sync operations.
Only accessible to users with admin role.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.database import get_db
from backend.app import models, schemas
from backend.app.auth import get_current_admin_user


router = APIRouter(prefix="/admin/bank-providers", tags=["admin"])


@router.get("/", response_model=List[schemas.BankProvider])
def list_providers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    """
    List all bank providers.

    Returns all providers with their configuration (API keys masked).
    """
    providers = db.query(models.BankProvider).all()
    return providers


@router.post("/", response_model=schemas.BankProvider)
def create_provider(
    provider: schemas.BankProviderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    """
    Create a new bank provider configuration.

    Admin can add additional providers beyond the seeded ones.
    """
    # Check if provider with same name already exists
    existing = db.query(models.BankProvider).filter(
        models.BankProvider.name == provider.name
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider.name}' already exists"
        )

    db_provider = models.BankProvider(
        name=provider.name,
        display_name=provider.display_name,
        environment=provider.environment,
        config_data=provider.config_data or "{}",
        authorization_url=provider.authorization_url,
        token_url=provider.token_url,
        api_base_url=provider.api_base_url,
        config_notes=provider.config_notes,
        is_active=False  # Admin must explicitly activate
    )

    db.add(db_provider)
    db.commit()
    db.refresh(db_provider)

    return db_provider


@router.put("/{provider_id}", response_model=schemas.BankProvider)
def update_provider(
    provider_id: int,
    provider_update: schemas.BankProviderUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    """
    Update bank provider configuration.

    Admin can update API keys, URLs, and activate/deactivate providers.
    """
    db_provider = db.query(models.BankProvider).get(provider_id)
    if not db_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    # Update fields if provided
    if provider_update.display_name is not None:
        db_provider.display_name = provider_update.display_name
    if provider_update.is_active is not None:
        db_provider.is_active = provider_update.is_active
    if provider_update.environment is not None:
        db_provider.environment = provider_update.environment
    if provider_update.config_data is not None:
        db_provider.config_data = provider_update.config_data
    if provider_update.authorization_url is not None:
        db_provider.authorization_url = provider_update.authorization_url
    if provider_update.token_url is not None:
        db_provider.token_url = provider_update.token_url
    if provider_update.api_base_url is not None:
        db_provider.api_base_url = provider_update.api_base_url
    if provider_update.config_notes is not None:
        db_provider.config_notes = provider_update.config_notes

    db.commit()
    db.refresh(db_provider)

    return db_provider


@router.delete("/{provider_id}")
def delete_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    """
    Delete a bank provider.

    Only allowed if no active connections use this provider.
    """
    db_provider = db.query(models.BankProvider).get(provider_id)
    if not db_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )

    # Check for active connections
    active_connections = db.query(models.BankConnection).filter(
        models.BankConnection.provider_id == provider_id,
        models.BankConnection.status == models.BankConnectionStatus.ACTIVE
    ).count()

    if active_connections > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete provider with {active_connections} active connections"
        )

    db.delete(db_provider)
    db.commit()

    return {"message": "Provider deleted successfully"}


@router.get("/stats")
def get_provider_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    Get statistics about bank integrations.

    Returns:
    - Total connections per provider
    - Sync success rates
    - Recent sync activity
    """
    from sqlalchemy import func, desc
    from datetime import datetime, timedelta

    # Total connections per provider
    connections_by_provider = db.query(
        models.BankProvider.name,
        models.BankProvider.display_name,
        func.count(models.BankConnection.id).label('connection_count')
    ).outerjoin(
        models.BankConnection,
        models.BankProvider.id == models.BankConnection.provider_id
    ).group_by(
        models.BankProvider.id
    ).all()

    # Sync statistics (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    total_syncs = db.query(models.BankSyncLog).filter(
        models.BankSyncLog.started_at >= thirty_days_ago
    ).count()

    successful_syncs = db.query(models.BankSyncLog).filter(
        models.BankSyncLog.started_at >= thirty_days_ago,
        models.BankSyncLog.sync_status == models.BankSyncStatus.SUCCESS
    ).count()

    # Recent sync logs
    recent_syncs = db.query(models.BankSyncLog).order_by(
        desc(models.BankSyncLog.started_at)
    ).limit(10).all()

    # Total transactions imported
    total_imported = db.query(
        func.sum(models.BankSyncLog.transactions_imported)
    ).scalar() or 0

    return {
        'providers': [
            {
                'name': p.name,
                'display_name': p.display_name,
                'connections': p.connection_count
            }
            for p in connections_by_provider
        ],
        'sync_stats': {
            'total_syncs_30d': total_syncs,
            'successful_syncs_30d': successful_syncs,
            'success_rate': round(successful_syncs / total_syncs * 100, 2) if total_syncs > 0 else 0,
            'total_transactions_imported': total_imported
        },
        'recent_syncs': [
            {
                'id': log.id,
                'connection_id': log.bank_connection_id,
                'started_at': log.started_at,
                'status': log.sync_status.value,
                'transactions_fetched': log.transactions_fetched,
                'transactions_imported': log.transactions_imported,
                'error_message': log.error_message
            }
            for log in recent_syncs
        ]
    }
