from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List
from decimal import Decimal

from backend.database import get_db
from ..models import User, Ledger, Budget, BudgetLine, JournalEntry, Account, Transaction
from ..schemas import (
    Budget as BudgetSchema,
    BudgetCreate,
    BudgetLine as BudgetLineSchema,
    BudgetLineInput
)
from ..auth import get_current_active_user, get_current_ledger

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/", response_model=List[BudgetSchema])
def list_budgets(
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    db: Session = Depends(get_db)
):
    """List all budgets for current ledger"""
    budgets = db.query(Budget).filter(
        Budget.ledger_id == current_ledger.id
    ).order_by(Budget.year.desc()).all()

    return budgets


@router.post("/", response_model=BudgetSchema)
def create_budget(
    budget: BudgetCreate,
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    db: Session = Depends(get_db)
):
    """Create a new budget"""
    db_budget = Budget(
        ledger_id=current_ledger.id,
        name=budget.name,
        year=budget.year,
        created_by=current_user.id
    )

    db.add(db_budget)
    db.commit()
    db.refresh(db_budget)

    return db_budget


@router.get("/{budget_id}", response_model=BudgetSchema)
def get_budget(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    db: Session = Depends(get_db)
):
    """Get budget with all lines"""
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.ledger_id == current_ledger.id
    ).first()

    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    return budget


@router.post("/{budget_id}/lines")
def set_budget_lines(
    budget_id: int,
    lines_input: List[BudgetLineInput],
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    db: Session = Depends(get_db)
):
    """Set budget lines for accounts with distribution options"""
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.ledger_id == current_ledger.id
    ).first()

    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    for line_input in lines_input:
        # Delete existing lines for this account
        db.query(BudgetLine).filter(
            BudgetLine.budget_id == budget_id,
            BudgetLine.account_id == line_input.account_id
        ).delete()

        # Calculate monthly amounts based on distribution type
        monthly_amounts = []

        if line_input.distribution_type == 'same':
            # Same amount for all 12 months
            monthly_amounts = [line_input.amount] * 12

        elif line_input.distribution_type == 'total':
            # Total divided by 12 months
            monthly_amount = line_input.amount / 12
            monthly_amounts = [monthly_amount] * 12

        elif line_input.distribution_type == 'manual':
            # Manual amounts provided (must be 12 values)
            if not line_input.monthly_amounts or len(line_input.monthly_amounts) != 12:
                raise HTTPException(
                    status_code=400,
                    detail="Manual distribution requires exactly 12 monthly amounts"
                )
            monthly_amounts = line_input.monthly_amounts

        else:
            raise HTTPException(status_code=400, detail="Invalid distribution_type")

        # Create budget lines for each month
        for month in range(1, 13):
            budget_line = BudgetLine(
                budget_id=budget_id,
                account_id=line_input.account_id,
                period=month,
                amount=monthly_amounts[month - 1]
            )
            db.add(budget_line)

    db.commit()

    return {"message": "Budget lines updated"}


@router.get("/{budget_id}/report")
def get_budget_report(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    db: Session = Depends(get_db)
):
    """Get budget vs actual report for all months"""
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.ledger_id == current_ledger.id
    ).first()

    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    # Get all budget lines grouped by account
    budget_lines = db.query(BudgetLine).filter(
        BudgetLine.budget_id == budget_id
    ).all()

    # Group budget lines by account_id
    budget_by_account = {}
    for line in budget_lines:
        if line.account_id not in budget_by_account:
            budget_by_account[line.account_id] = {}
        budget_by_account[line.account_id][line.period] = float(line.amount)

    # Get actual amounts from journal entries for this year
    actual_query = db.query(
        JournalEntry.account_id,
        extract('month', Transaction.transaction_date).label('month'),
        func.sum(JournalEntry.debit - JournalEntry.credit).label('amount')
    ).join(
        Transaction, JournalEntry.transaction_id == Transaction.id
    ).filter(
        Transaction.ledger_id == current_ledger.id,
        extract('year', Transaction.transaction_date) == budget.year
    ).group_by(
        JournalEntry.account_id,
        'month'
    ).all()

    # Group actual amounts by account_id and month
    actual_by_account = {}
    for row in actual_query:
        if row.account_id not in actual_by_account:
            actual_by_account[row.account_id] = {}
        actual_by_account[row.account_id][int(row.month)] = float(row.amount)

    # Get account details
    all_account_ids = set(budget_by_account.keys()) | set(actual_by_account.keys())
    accounts = db.query(Account).filter(
        Account.id.in_(all_account_ids)
    ).all()
    account_map = {acc.id: acc for acc in accounts}

    # Build report data
    report_lines = []
    for account_id in sorted(all_account_ids, key=lambda aid: account_map[aid].account_number if aid in account_map else str(aid)):
        account = account_map.get(account_id)
        line = {
            'account_id': account_id,
            'account_number': account.account_number if account else str(account_id),
            'account_name': account.account_name if account else 'Unknown',
            'account_type': account.account_type.value if account else 'EXPENSE',
            'months': []
        }

        total_budget = 0
        total_actual = 0

        for month in range(1, 13):
            budget_amount = budget_by_account.get(account_id, {}).get(month, 0)
            actual_amount = actual_by_account.get(account_id, {}).get(month, 0)
            variance = actual_amount - budget_amount

            total_budget += budget_amount
            total_actual += actual_amount

            line['months'].append({
                'month': month,
                'budget': budget_amount,
                'actual': actual_amount,
                'variance': variance
            })

        line['total_budget'] = total_budget
        line['total_actual'] = total_actual
        line['total_variance'] = total_actual - total_budget

        report_lines.append(line)

    return {
        'budget': budget,
        'lines': report_lines
    }


@router.get("/{budget_id}/drilldown")
def get_budget_drilldown(
    budget_id: int,
    account_id: int = None,
    month: int = None,
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    db: Session = Depends(get_db)
):
    """Get transactions for a specific account and month in a budget year"""
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.ledger_id == current_ledger.id
    ).first()

    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    if not account_id:
        raise HTTPException(status_code=400, detail="account_id required")

    query = db.query(
        Transaction.id,
        Transaction.transaction_date,
        Transaction.description,
        Transaction.status,
        JournalEntry.debit,
        JournalEntry.credit
    ).join(
        JournalEntry, JournalEntry.transaction_id == Transaction.id
    ).filter(
        Transaction.ledger_id == current_ledger.id,
        JournalEntry.account_id == account_id,
        extract('year', Transaction.transaction_date) == budget.year
    )

    if month:
        query = query.filter(
            extract('month', Transaction.transaction_date) == month
        )

    rows = query.order_by(Transaction.transaction_date).all()

    return [{
        'id': r.id,
        'date': r.transaction_date.isoformat(),
        'description': r.description,
        'status': r.status.value if hasattr(r.status, 'value') else r.status,
        'debit': float(r.debit),
        'credit': float(r.credit),
        'amount': float(r.debit - r.credit)
    } for r in rows]


@router.delete("/{budget_id}")
def delete_budget(
    budget_id: int,
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
    db: Session = Depends(get_db)
):
    """Delete a budget"""
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.ledger_id == current_ledger.id
    ).first()

    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    db.delete(budget)
    db.commit()

    return {"message": "Budget deleted"}
