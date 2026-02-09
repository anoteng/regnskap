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
from typing import List, Optional, Dict
from datetime import date, datetime

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
        external_bank_id=connection_request.external_bank_id,
        initial_sync_from_date=connection_request.initial_sync_from_date
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
    Exchanges code for tokens and redirects to account selection page.
    """
    import os
    from urllib.parse import urlencode
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:8002')
    redirect_uri = f"{frontend_url}/api/bank-connections/oauth/callback"

    try:
        service = BankIntegrationService(db)
        result = await service.handle_oauth_callback(
            state_token=state,
            authorization_code=code,
            redirect_uri=redirect_uri
        )

        # Redirect to account selection page with state token
        query_params = urlencode({'state': result['state_token']})
        return RedirectResponse(
            url=f"{frontend_url}/bank-connection-select.html?{query_params}"
        )

    except ValueError as e:
        # Invalid state, expired, or already used
        return RedirectResponse(
            url=f"{frontend_url}/bank-connections.html?error=invalid_state&message={str(e)}"
        )
    except Exception as e:
        # Other errors (token exchange failed, etc.)
        return RedirectResponse(
            url=f"{frontend_url}/bank-connections.html?error=connection_failed&message={str(e)}"
        )


@router.post("/select-account")
async def select_account(
    request: schemas.AccountSelectionRequest,
    db: Session = Depends(get_db)
):
    """
    Create bank connection after user selects account.

    Called from account selection page after OAuth callback.

    Example:
        POST /bank-connections/select-account
        {
            "state_token": "abc123",
            "selected_account_id": "account-uuid-456"
        }

        Response:
        {
            "success": true,
            "connection_id": 1,
            "message": "Bank connected successfully"
        }
    """
    try:
        service = BankIntegrationService(db)
        bank_connection = await service.create_connection_from_selection(
            state_token=request.state_token,
            selected_account_id=request.selected_account_id,
            bank_account_id=request.bank_account_id
        )

        return {
            "success": True,
            "connection_id": bank_connection.id,
            "message": "Bank connected successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create connection: {str(e)}"
        )


@router.get("/accounts-for-selection")
async def get_accounts_for_selection(
    state_token: str = Query(..., description="OAuth state token"),
    db: Session = Depends(get_db)
):
    """
    Get available accounts for selection.

    Called by account selection page to show user which accounts they can connect.

    Example:
        GET /bank-connections/accounts-for-selection?state_token=abc123

        Response:
        {
            "accounts": [
                {
                    "account_id": "uuid-123",
                    "account_name": "Felleskonto (SavingsAccount)",
                    "iban": "93551582505",
                    "currency": "NOK"
                },
                {
                    "account_id": "uuid-456",
                    "account_name": "Kredittkort (CreditCard)",
                    "iban": null,
                    "currency": "NOK"
                }
            ],
            "bank_account_id": 1
        }
    """
    # Validate state token and get stored accounts
    oauth_state = db.query(models.OAuthState).filter(
        models.OAuthState.state_token == state_token
    ).first()

    if not oauth_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid state token"
        )

    # Allow reusing state for multiple accounts
    # if oauth_state.used_at:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="State token already used"
    #     )

    # Use UTC for consistency with service.py
    if oauth_state.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token expired"
        )

    if not oauth_state.accounts_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account data available"
        )

    # Parse accounts data
    import json
    stored_data = json.loads(oauth_state.accounts_data)
    accounts = stored_data['accounts']

    # Fetch available bank accounts from the ledger
    bank_accounts = db.query(models.BankAccount).filter(
        models.BankAccount.ledger_id == oauth_state.ledger_id,
        models.BankAccount.is_active == True
    ).all()

    # Convert to dict format
    bank_accounts_list = [
        {
            "id": ba.id,
            "name": ba.name,
            "account_number": ba.account_number,
            "account_type": ba.account_type
        }
        for ba in bank_accounts
    ]

    return {
        "accounts": accounts,
        "bank_accounts": bank_accounts_list,
        "bank_account_id": oauth_state.bank_account_id
    }


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


@router.post("/{connection_id}/reauthorize", response_model=schemas.OAuthInitiateResponse)
async def reauthorize_bank_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    current_ledger: models.Ledger = Depends(get_current_ledger)
):
    """
    Re-authorize an existing bank connection.

    This is useful when:
    - Session has expired (EXPIRED_SESSION error)
    - ASPSP_ERROR occurs due to stale session
    - Account IDs need to be refreshed

    Returns new authorization URL. After user authorizes, the existing
    connection will be updated with new tokens and account IDs.
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

    # Get associated bank account
    bank_account = db.query(models.BankAccount).get(connection.bank_account_id)
    if not bank_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated bank account not found"
        )

    # Note: Connection status will be updated to ACTIVE after successful re-authorization
    # in the account selection flow

    # Build redirect URI
    import os
    base_url = os.getenv('FRONTEND_URL', 'http://localhost:8002')
    redirect_uri = f"{base_url}/api/bank-connections/oauth/callback"

    # Start OAuth flow (will update existing connection via bank_account_id)
    # Use the same ASPSP (bank) as the original connection
    service = BankIntegrationService(db)
    result = await service.start_oauth_flow(
        user=current_user,
        ledger=current_ledger,
        bank_account=bank_account,
        provider_id=connection.provider_id,
        redirect_uri=redirect_uri,
        external_bank_id=connection.external_bank_id  # Use stored bank ID
    )

    return result


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
