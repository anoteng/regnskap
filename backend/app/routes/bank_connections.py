"""
Bank Connection Routes

User-facing endpoints for:
- Connecting bank accounts
- OAuth callback handling
- Syncing transactions
- Disconnecting banks
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from backend.database import get_db
from backend.app import models, schemas
from backend.app.auth import get_current_active_user, get_current_ledger
from backend.app.bank_integration.service import BankIntegrationService


router = APIRouter(prefix="/bank-connections", tags=["bank-connections"])


@router.get("/providers")
def list_available_providers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
) -> List[Dict]:
    """
    List available bank providers for connection.

    Returns only active providers.
    """
    providers = db.query(models.BankProvider).filter(
        models.BankProvider.is_active == True
    ).all()

    return [
        {
            'id': p.id,
            'name': p.name,
            'display_name': p.display_name,
            'environment': p.environment
        }
        for p in providers
    ]


@router.post("/connect", response_model=schemas.OAuthInitiateResponse)
async def initiate_bank_connection(
    connection_request: schemas.BankConnectionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    current_ledger: models.Ledger = Depends(get_current_ledger)
):
    """
    Initiate OAuth flow for connecting a bank account.

    Returns authorization URL that user should be redirected to.

    Example:
        POST /bank-connections/connect
        {
            "bank_account_id": 1,
            "provider_id": 1,
            "external_bank_id": "NO_DNB"  // Optional
        }

        Response:
        {
            "authorization_url": "https://api.enablebanking.com/auth?...",
            "state_token": "abc123..."
        }
    """
    # Verify bank account exists and belongs to current ledger
    bank_account = db.query(models.BankAccount).get(connection_request.bank_account_id)
    if not bank_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found"
        )

    if bank_account.ledger_id != current_ledger.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bank account does not belong to current ledger"
        )

    # Check if already connected
    existing = db.query(models.BankConnection).filter(
        models.BankConnection.bank_account_id == connection_request.bank_account_id,
        models.BankConnection.status == models.BankConnectionStatus.ACTIVE
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bank account already connected. Disconnect first to reconnect."
        )

    # Verify provider exists and is active
    provider = db.query(models.BankProvider).get(connection_request.provider_id)
    if not provider or not provider.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found or not active"
        )

    # Build redirect URI (should be configured based on environment)
    # For now, assume it's the current domain + /bank-connections/oauth/callback
    import os
    base_url = os.getenv('FRONTEND_URL', 'http://localhost:8002')
    redirect_uri = f"{base_url}/api/bank-connections/oauth/callback"

    # Start OAuth flow
    service = BankIntegrationService(db)
    result = await service.start_oauth_flow(
        user=current_user,
        ledger=current_ledger,
        bank_account=bank_account,
        provider_id=connection_request.provider_id,
        redirect_uri=redirect_uri,
        external_bank_id=connection_request.external_bank_id
    )

    return result


@router.get("/oauth/callback")
async def oauth_callback(
    state: str = Query(..., description="CSRF state token"),
    code: str = Query(..., description="Authorization code"),
    db: Session = Depends(get_db)
):
    """
    OAuth callback endpoint.

    Bank redirects user here after authorization.
    Completes OAuth flow and creates bank connection.

    Redirects to frontend with success/error status.
    """
    import os
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:8002')
    redirect_uri = f"{frontend_url}/api/bank-connections/oauth/callback"

    try:
        service = BankIntegrationService(db)
        bank_connection = await service.handle_oauth_callback(
            state_token=state,
            authorization_code=code,
            redirect_uri=redirect_uri
        )

        # Trigger initial sync in background (optional)
        # For now, redirect to frontend and let user trigger sync manually

        # Redirect to frontend success page
        return RedirectResponse(
            url=f"{frontend_url}/bank-connections?success=true&connection_id={bank_connection.id}"
        )

    except ValueError as e:
        # Invalid state, expired, or already used
        return RedirectResponse(
            url=f"{frontend_url}/bank-connections?error=invalid_state&message={str(e)}"
        )
    except Exception as e:
        # Other errors (token exchange failed, etc.)
        return RedirectResponse(
            url=f"{frontend_url}/bank-connections?error=connection_failed&message={str(e)}"
        )


@router.get("/", response_model=List[schemas.BankConnection])
def list_connections(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    current_ledger: models.Ledger = Depends(get_current_ledger)
):
    """
    List user's bank connections for current ledger.

    Returns all connections (active and disconnected).
    """
    connections = db.query(models.BankConnection).filter(
        models.BankConnection.ledger_id == current_ledger.id
    ).all()

    return connections


@router.post("/{connection_id}/sync", response_model=schemas.SyncResponse)
async def manual_sync(
    connection_id: int,
    sync_params: Optional[schemas.SyncParams] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    current_ledger: models.Ledger = Depends(get_current_ledger)
):
    """
    Manually trigger transaction sync for a connection.

    Optional date range can be specified, otherwise syncs from last sync.

    Example:
        POST /bank-connections/1/sync
        {
            "from_date": "2024-01-01",
            "to_date": "2024-01-31"
        }

        Response:
        {
            "status": "success",
            "transactions_fetched": 15,
            "imported": 12,
            "duplicates": 3,
            "message": null
        }
    """
    # Verify connection exists and belongs to current ledger
    connection = db.query(models.BankConnection).get(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )

    if connection.ledger_id != current_ledger.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Connection does not belong to current ledger"
        )

    if connection.status == models.BankConnectionStatus.DISCONNECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection is disconnected. Reconnect first."
        )

    # Sync transactions
    service = BankIntegrationService(db)

    from_date = sync_params.from_date if sync_params else None
    to_date = sync_params.to_date if sync_params else None

    result = await service.sync_transactions(
        bank_connection=connection,
        user=current_user,
        from_date=from_date,
        to_date=to_date,
        sync_type=models.BankSyncType.MANUAL
    )

    # Build response
    message = None
    if result['errors']:
        message = f"{len(result['errors'])} errors occurred"

    return schemas.SyncResponse(
        status=result['status'],
        transactions_fetched=result['transactions_fetched'],
        imported=result['imported'],
        duplicates=result['duplicates'],
        message=message
    )


@router.delete("/{connection_id}")
async def disconnect_bank(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    current_ledger: models.Ledger = Depends(get_current_ledger)
):
    """
    Disconnect bank account.

    Revokes OAuth tokens and marks connection as disconnected.
    """
    # Verify connection exists and belongs to current ledger
    connection = db.query(models.BankConnection).get(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )

    if connection.ledger_id != current_ledger.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Connection does not belong to current ledger"
        )

    # Disconnect
    service = BankIntegrationService(db)
    await service.disconnect_bank(connection, current_user)

    return {"message": "Bank disconnected successfully"}


@router.get("/{connection_id}/logs", response_model=List[schemas.BankSyncLog])
def get_sync_logs(
    connection_id: int,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    current_ledger: models.Ledger = Depends(get_current_ledger)
):
    """
    Get sync history for a connection.

    Returns recent sync logs with results and error messages.
    """
    from sqlalchemy import desc

    # Verify connection exists and belongs to current ledger
    connection = db.query(models.BankConnection).get(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )

    if connection.ledger_id != current_ledger.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Connection does not belong to current ledger"
        )

    # Get logs
    logs = db.query(models.BankSyncLog).filter(
        models.BankSyncLog.bank_connection_id == connection_id
    ).order_by(
        desc(models.BankSyncLog.started_at)
    ).limit(limit).all()

    return logs


@router.get("/{connection_id}/transactions", response_model=List[schemas.BankTransaction])
def get_fetched_transactions(
    connection_id: int,
    status: Optional[str] = Query(None, description="Filter by import status"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    current_ledger: models.Ledger = Depends(get_current_ledger)
):
    """
    Get fetched transactions for a connection.

    Useful for debugging and reviewing what was imported.
    """
    from sqlalchemy import desc

    # Verify connection exists and belongs to current ledger
    connection = db.query(models.BankConnection).get(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )

    if connection.ledger_id != current_ledger.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Connection does not belong to current ledger"
        )

    # Build query
    query = db.query(models.BankTransaction).filter(
        models.BankTransaction.bank_connection_id == connection_id
    )

    # Filter by status if specified
    if status:
        try:
            import_status = models.BankTransactionImportStatus(status)
            query = query.filter(models.BankTransaction.import_status == import_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid import status: {status}"
            )

    # Get transactions
    transactions = query.order_by(
        desc(models.BankTransaction.transaction_date)
    ).limit(limit).all()

    return transactions
