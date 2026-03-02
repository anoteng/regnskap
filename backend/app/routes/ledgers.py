from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from ..models import (
    User, Ledger, LedgerMember, LedgerRole, Account,
    ChartOfAccountsTemplate, TemplateAccount
)
from ..schemas import (
    Ledger as LedgerSchema,
    LedgerCreate,
    LedgerWithRole,
    LedgerMember as LedgerMemberSchema,
    LedgerMemberCreate
)
from ..auth import get_current_active_user, get_current_ledger, require_ledger_owner, get_user_role_in_ledger

router = APIRouter(prefix="/ledgers", tags=["ledgers"])


@router.get("/", response_model=List[LedgerWithRole])
async def list_user_ledgers(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all ledgers the current user has access to."""
    memberships = db.query(LedgerMember).filter(
        LedgerMember.user_id == current_user.id
    ).all()

    ledgers_with_roles = []
    for membership in memberships:
        ledger = db.query(Ledger).filter(
            Ledger.id == membership.ledger_id,
            Ledger.is_active == True
        ).first()

        if ledger:
            ledger_dict = {
                "id": ledger.id,
                "name": ledger.name,
                "created_by": ledger.created_by,
                "created_at": ledger.created_at,
                "is_active": ledger.is_active,
                "user_role": membership.role.value
            }
            ledgers_with_roles.append(ledger_dict)

    return ledgers_with_roles


@router.post("/", response_model=LedgerSchema)
async def create_ledger(
    ledger: LedgerCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new ledger."""
    # If no template specified, use the default one
    chart_template_id = ledger.chart_template_id
    if chart_template_id is None:
        default_template = db.query(ChartOfAccountsTemplate).filter(
            ChartOfAccountsTemplate.is_default == True,
            ChartOfAccountsTemplate.is_active == True
        ).first()
        if default_template:
            chart_template_id = default_template.id

    # Create the ledger
    db_ledger = Ledger(
        name=ledger.name,
        created_by=current_user.id,
        chart_template_id=chart_template_id
    )
    db.add(db_ledger)
    db.commit()
    db.refresh(db_ledger)

    # Copy accounts from template
    if chart_template_id:
        _copy_accounts_from_template(db, db_ledger.id, chart_template_id)

    # Add creator as owner
    membership = LedgerMember(
        ledger_id=db_ledger.id,
        user_id=current_user.id,
        role=LedgerRole.OWNER
    )
    db.add(membership)

    # Set as user's active ledger if they don't have one
    if current_user.last_active_ledger_id is None:
        current_user.last_active_ledger_id = db_ledger.id

    db.commit()
    db.refresh(db_ledger)

    return db_ledger


def _copy_accounts_from_template(db: Session, ledger_id: int, template_id: int):
    """Copy accounts from a template to a ledger."""
    # Get all template accounts that should be included by default
    template_accounts = db.query(TemplateAccount).filter(
        TemplateAccount.template_id == template_id,
        TemplateAccount.is_default == True
    ).order_by(TemplateAccount.sort_order).all()

    # Map of account_number -> created Account object (for parent relationships)
    account_map = {}

    # First pass: create all accounts without parent relationships
    for template_account in template_accounts:
        account = Account(
            ledger_id=ledger_id,
            account_number=template_account.account_number,
            account_name=template_account.account_name,
            account_type=template_account.account_type,
            description=template_account.description,
            is_active=True
        )
        db.add(account)
        db.flush()  # Get the ID without committing
        account_map[template_account.account_number] = account

    # Second pass: set up parent relationships
    for template_account in template_accounts:
        if template_account.parent_account_number:
            parent_account = account_map.get(template_account.parent_account_number)
            if parent_account:
                child_account = account_map[template_account.account_number]
                child_account.parent_account_id = parent_account.id

    db.commit()


@router.get("/{ledger_id}", response_model=LedgerWithRole)
async def get_ledger(
    ledger_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get ledger details."""
    ledger = db.query(Ledger).filter(Ledger.id == ledger_id, Ledger.is_active == True).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger not found")

    # Verify user has access
    role = get_user_role_in_ledger(db, current_user.id, ledger_id)
    if not role:
        raise HTTPException(status_code=403, detail="You do not have access to this ledger")

    return {
        "id": ledger.id,
        "name": ledger.name,
        "created_by": ledger.created_by,
        "created_at": ledger.created_at,
        "is_active": ledger.is_active,
        "user_role": role.value
    }


@router.put("/{ledger_id}", response_model=LedgerSchema)
async def update_ledger(
    ledger_id: int,
    ledger_update: LedgerCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update ledger details (owner only)."""
    ledger = db.query(Ledger).filter(Ledger.id == ledger_id, Ledger.is_active == True).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger not found")

    # Verify user is owner
    role = get_user_role_in_ledger(db, current_user.id, ledger_id)
    if role != LedgerRole.OWNER:
        raise HTTPException(status_code=403, detail="Only ledger owners can update ledger details")

    ledger.name = ledger_update.name
    db.commit()
    db.refresh(ledger)

    return ledger


@router.delete("/{ledger_id}")
async def delete_ledger(
    ledger_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a ledger (owner only)."""
    ledger = db.query(Ledger).filter(Ledger.id == ledger_id, Ledger.is_active == True).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger not found")

    # Verify user is owner
    role = get_user_role_in_ledger(db, current_user.id, ledger_id)
    if role != LedgerRole.OWNER:
        raise HTTPException(status_code=403, detail="Only ledger owners can delete ledgers")

    # Soft delete
    ledger.is_active = False

    # If this was user's active ledger, clear it
    if current_user.last_active_ledger_id == ledger_id:
        current_user.last_active_ledger_id = None

    db.commit()

    return {"message": "Ledger deleted successfully"}


@router.post("/{ledger_id}/switch")
async def switch_ledger(
    ledger_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Switch to this ledger (update last_active)."""
    ledger = db.query(Ledger).filter(Ledger.id == ledger_id, Ledger.is_active == True).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger not found")

    # Verify user has access
    role = get_user_role_in_ledger(db, current_user.id, ledger_id)
    if not role:
        raise HTTPException(status_code=403, detail="You do not have access to this ledger")

    # Update last active ledger
    current_user.last_active_ledger_id = ledger_id
    db.commit()

    return {"message": "Switched to ledger successfully", "ledger_id": ledger_id}


@router.get("/{ledger_id}/members", response_model=List[LedgerMemberSchema])
async def list_ledger_members(
    ledger_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all members of a ledger."""
    # Verify user has access to this ledger
    role = get_user_role_in_ledger(db, current_user.id, ledger_id)
    if not role:
        raise HTTPException(status_code=403, detail="You do not have access to this ledger")

    memberships = db.query(LedgerMember).filter(LedgerMember.ledger_id == ledger_id).all()

    result = []
    for membership in memberships:
        user = db.query(User).filter(User.id == membership.user_id).first()
        if user:
            result.append({
                "ledger_id": membership.ledger_id,
                "user_id": membership.user_id,
                "role": membership.role.value,
                "joined_at": membership.joined_at,
                "user": user
            })

    return result


@router.post("/{ledger_id}/members")
async def invite_member(
    ledger_id: int,
    member_invite: LedgerMemberCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Invite a member to the ledger (owner only)."""
    # Verify user is owner
    role = get_user_role_in_ledger(db, current_user.id, ledger_id)
    if role != LedgerRole.OWNER:
        raise HTTPException(status_code=403, detail="Only ledger owners can invite members")

    # Find user by email
    invited_user = db.query(User).filter(User.email == member_invite.email).first()
    if not invited_user:
        raise HTTPException(status_code=404, detail="User not found with that email")

    # Check if already a member
    existing_membership = db.query(LedgerMember).filter(
        LedgerMember.ledger_id == ledger_id,
        LedgerMember.user_id == invited_user.id
    ).first()

    if existing_membership:
        raise HTTPException(status_code=400, detail="User is already a member of this ledger")

    # Validate role
    try:
        invited_role = LedgerRole[member_invite.role]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid role")

    # Create membership
    membership = LedgerMember(
        ledger_id=ledger_id,
        user_id=invited_user.id,
        role=invited_role
    )
    db.add(membership)
    db.commit()

    return {"message": "Member invited successfully", "user_id": invited_user.id}


@router.put("/{ledger_id}/members/{user_id}")
async def update_member_role(
    ledger_id: int,
    user_id: int,
    role_update: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a member's role (owner only)."""
    # Verify current user is owner
    current_role = get_user_role_in_ledger(db, current_user.id, ledger_id)
    if current_role != LedgerRole.OWNER:
        raise HTTPException(status_code=403, detail="Only ledger owners can update member roles")

    # Can't change your own role
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    # Get membership
    membership = db.query(LedgerMember).filter(
        LedgerMember.ledger_id == ledger_id,
        LedgerMember.user_id == user_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")

    # Validate new role
    try:
        new_role = LedgerRole[role_update.get("role")]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid role")

    membership.role = new_role
    db.commit()

    return {"message": "Member role updated successfully"}


@router.delete("/{ledger_id}/members/{user_id}")
async def remove_member(
    ledger_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Remove a member from the ledger (owner only)."""
    # Verify current user is owner
    current_role = get_user_role_in_ledger(db, current_user.id, ledger_id)
    if current_role != LedgerRole.OWNER:
        raise HTTPException(status_code=403, detail="Only ledger owners can remove members")

    # Can't remove yourself (use leave endpoint instead)
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself. Use the leave endpoint instead.")

    # Get membership
    membership = db.query(LedgerMember).filter(
        LedgerMember.ledger_id == ledger_id,
        LedgerMember.user_id == user_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")

    # Remove membership
    db.delete(membership)

    # If this was the user's active ledger, clear it
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.last_active_ledger_id == ledger_id:
        user.last_active_ledger_id = None

    db.commit()

    return {"message": "Member removed successfully"}


@router.post("/{ledger_id}/leave")
async def leave_ledger(
    ledger_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Leave a ledger (if not owner)."""
    # Get membership
    membership = db.query(LedgerMember).filter(
        LedgerMember.ledger_id == ledger_id,
        LedgerMember.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="You are not a member of this ledger")

    # Can't leave if you're the owner
    if membership.role == LedgerRole.OWNER:
        raise HTTPException(
            status_code=400,
            detail="Cannot leave ledger as owner. Transfer ownership or delete the ledger instead."
        )

    # Remove membership
    db.delete(membership)

    # If this was user's active ledger, clear it
    if current_user.last_active_ledger_id == ledger_id:
        current_user.last_active_ledger_id = None

    db.commit()

    return {"message": "Left ledger successfully"}
