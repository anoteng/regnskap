from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from ..models import (
    User, ChartOfAccountsTemplate, TemplateAccount
)
from ..schemas import (
    ChartOfAccountsTemplate as ChartOfAccountsTemplateSchema,
    ChartOfAccountsTemplateCreate,
    TemplateAccount as TemplateAccountSchema,
    TemplateAccountBase,
    TemplateAccountCreate
)
from ..auth import get_current_active_user, get_current_admin_user

router = APIRouter(prefix="/chart-templates", tags=["chart-templates"])


@router.get("/", response_model=List[ChartOfAccountsTemplateSchema])
async def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all available chart of accounts templates."""
    templates = db.query(ChartOfAccountsTemplate).filter(
        ChartOfAccountsTemplate.is_active == True
    ).all()
    return templates


@router.get("/{template_id}", response_model=ChartOfAccountsTemplateSchema)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific template."""
    template = db.query(ChartOfAccountsTemplate).filter(
        ChartOfAccountsTemplate.id == template_id,
        ChartOfAccountsTemplate.is_active == True
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.get("/{template_id}/accounts", response_model=List[TemplateAccountSchema])
async def list_template_accounts(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all accounts in a template."""
    # Verify template exists
    template = db.query(ChartOfAccountsTemplate).filter(
        ChartOfAccountsTemplate.id == template_id,
        ChartOfAccountsTemplate.is_active == True
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    accounts = db.query(TemplateAccount).filter(
        TemplateAccount.template_id == template_id
    ).order_by(TemplateAccount.sort_order).all()

    return accounts


@router.post("/", response_model=ChartOfAccountsTemplateSchema)
async def create_template(
    template: ChartOfAccountsTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new chart of accounts template (admin only)."""
    # Check if template with this name already exists
    existing = db.query(ChartOfAccountsTemplate).filter(
        ChartOfAccountsTemplate.name == template.name
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Template with this name already exists"
        )

    # If this is set as default, unset any other default
    if template.is_default:
        db.query(ChartOfAccountsTemplate).filter(
            ChartOfAccountsTemplate.is_default == True
        ).update({"is_default": False})

    db_template = ChartOfAccountsTemplate(**template.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)

    return db_template


@router.put("/{template_id}", response_model=ChartOfAccountsTemplateSchema)
async def update_template(
    template_id: int,
    template_update: ChartOfAccountsTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update a template (admin only)."""
    db_template = db.query(ChartOfAccountsTemplate).filter(
        ChartOfAccountsTemplate.id == template_id
    ).first()

    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    # If setting as default, unset any other default
    if template_update.is_default and not db_template.is_default:
        db.query(ChartOfAccountsTemplate).filter(
            ChartOfAccountsTemplate.is_default == True
        ).update({"is_default": False})

    for key, value in template_update.model_dump().items():
        setattr(db_template, key, value)

    db.commit()
    db.refresh(db_template)

    return db_template


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a template (admin only)."""
    db_template = db.query(ChartOfAccountsTemplate).filter(
        ChartOfAccountsTemplate.id == template_id
    ).first()

    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check if any ledgers are using this template
    from ..models import Ledger
    ledgers_using = db.query(Ledger).filter(
        Ledger.chart_template_id == template_id,
        Ledger.is_active == True
    ).count()

    if ledgers_using > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete template: {ledgers_using} ledger(s) are using it"
        )

    # Soft delete
    db_template.is_active = False
    db.commit()

    return {"message": "Template deleted successfully"}


@router.post("/{template_id}/accounts", response_model=TemplateAccountSchema)
async def create_template_account(
    template_id: int,
    account: TemplateAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Add an account to a template (admin only)."""
    # Verify template exists
    template = db.query(ChartOfAccountsTemplate).filter(
        ChartOfAccountsTemplate.id == template_id,
        ChartOfAccountsTemplate.is_active == True
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check if account number already exists in this template
    existing = db.query(TemplateAccount).filter(
        TemplateAccount.template_id == template_id,
        TemplateAccount.account_number == account.account_number
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Account with this number already exists in template"
        )

    db_account = TemplateAccount(**account.model_dump())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)

    return db_account


@router.put("/{template_id}/accounts/{account_id}", response_model=TemplateAccountSchema)
async def update_template_account(
    template_id: int,
    account_id: int,
    account_update: TemplateAccountBase,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update a template account (admin only)."""
    db_account = db.query(TemplateAccount).filter(
        TemplateAccount.id == account_id,
        TemplateAccount.template_id == template_id
    ).first()

    if not db_account:
        raise HTTPException(status_code=404, detail="Template account not found")

    for key, value in account_update.model_dump().items():
        setattr(db_account, key, value)

    db.commit()
    db.refresh(db_account)

    return db_account


@router.delete("/{template_id}/accounts/{account_id}")
async def delete_template_account(
    template_id: int,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a template account (admin only)."""
    db_account = db.query(TemplateAccount).filter(
        TemplateAccount.id == account_id,
        TemplateAccount.template_id == template_id
    ).first()

    if not db_account:
        raise HTTPException(status_code=404, detail="Template account not found")

    db.delete(db_account)
    db.commit()

    return {"message": "Template account deleted successfully"}
