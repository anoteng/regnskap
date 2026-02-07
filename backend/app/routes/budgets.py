from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List
from decimal import Decimal

from backend.database import get_db
from ..models import User, Ledger, Budget, BudgetLine, JournalEntry, Account
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
            BudgetLine.account_number == line_input.account_number
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
                account_number=line_input.account_number,
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

    # Group budget lines by account
    budget_by_account = {}
    for line in budget_lines:
        if line.account_number not in budget_by_account:
            budget_by_account[line.account_number] = {}
        budget_by_account[line.account_number][line.period] = float(line.amount)

    # Get actual amounts from journal entries for this year
    actual_query = db.query(
        JournalEntry.account_number,
        extract('month', JournalEntry.entry_date).label('month'),
        func.sum(JournalEntry.debit - JournalEntry.credit).label('amount')
    ).join(
        JournalEntry.transaction
    ).filter(
        JournalEntry.transaction.has(ledger_id=current_ledger.id),
        extract('year', JournalEntry.entry_date) == budget.year
    ).group_by(
        JournalEntry.account_number,
        'month'
    ).all()

    # Group actual amounts by account and month
    actual_by_account = {}
    for row in actual_query:
        if row.account_number not in actual_by_account:
            actual_by_account[row.account_number] = {}
        actual_by_account[row.account_number][int(row.month)] = float(row.amount)

    # Get account details
    all_account_numbers = set(budget_by_account.keys()) | set(actual_by_account.keys())
    accounts = db.query(Account).filter(
        Account.account_number.in_(all_account_numbers)
    ).all()
    account_map = {acc.account_number: acc for acc in accounts}

    # Build report data
    report_lines = []
    for account_number in sorted(all_account_numbers, key=lambda x: int(x) if x.isdigit() else x):
        account = account_map.get(account_number)
        line = {
            'account_number': account_number,
            'account_name': account.account_name if account else 'Unknown',
            'months': []
        }

        total_budget = 0
        total_actual = 0

        for month in range(1, 13):
            budget_amount = budget_by_account.get(account_number, {}).get(month, 0)
            actual_amount = actual_by_account.get(account_number, {}).get(month, 0)
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
