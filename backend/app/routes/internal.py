from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.config import get_settings
from ..models import BankConnection, User, BankConnectionStatus, BankSyncType

router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_sync_key(x_sync_key: str = Header(...)):
    settings = get_settings()
    if not settings.sync_api_key or x_sync_key != settings.sync_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid sync key")


@router.post("/sync-all")
async def sync_all_connections(
    db: Session = Depends(get_db),
    _: None = Depends(_verify_sync_key),
):
    """
    Trigger auto-sync for all active bank connections that are due.
    Called by the nightly systemd timer. Protected by X-Sync-Key header.
    """
    from ..bank_integration.service import BankIntegrationService

    now = datetime.now(timezone.utc)

    connections = db.query(BankConnection).filter(
        BankConnection.status == BankConnectionStatus.ACTIVE,
        BankConnection.auto_sync_enabled == True,
    ).all()

    results = []
    service = BankIntegrationService(db)

    for conn in connections:
        # Skip if synced too recently
        if conn.last_sync_at:
            last = conn.last_sync_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            hours_since = (now - last).total_seconds() / 3600
            if hours_since < conn.sync_frequency_hours:
                results.append({
                    'connection_id': conn.id,
                    'status': 'skipped',
                    'reason': f'synced {hours_since:.1f}h ago',
                })
                continue

        user = db.query(User).filter(User.id == conn.created_by).first()
        if not user:
            results.append({'connection_id': conn.id, 'status': 'failed', 'error': 'user not found'})
            continue

        try:
            result = await service.sync_transactions(
                bank_connection=conn,
                user=user,
                sync_type=BankSyncType.AUTO,
            )
            results.append({'connection_id': conn.id, **result})
        except Exception as e:
            results.append({'connection_id': conn.id, 'status': 'failed', 'error': str(e)})

    synced = sum(1 for r in results if r.get('status') not in ('skipped', 'failed'))
    return {'total': len(connections), 'synced': synced, 'results': results}
