from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from decimal import Decimal

from backend.database import get_db
from ..models import Account, JournalEntry, Transaction, User, Ledger
from ..schemas import BalanceSheet, IncomeStatement, BalanceSheetItem, IncomeStatementItem
from ..auth import get_current_active_user, get_current_ledger

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/balance-sheet", response_model=BalanceSheet)
def get_balance_sheet(
    as_of_date: date = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    if not as_of_date:
        as_of_date = date.today()

    assets = []
    liabilities = []
    equity = []

    asset_accounts = db.query(Account).filter(
        Account.account_type == "ASSET",
        Account.is_active == True
    ).all()

    for account in asset_accounts:
        balance = db.query(
            func.coalesce(func.sum(JournalEntry.debit - JournalEntry.credit), 0)
        ).join(
            JournalEntry.transaction
        ).filter(
            JournalEntry.account_id == account.id,
            Transaction.ledger_id == current_ledger.id,
            Transaction.transaction_date <= as_of_date
        ).scalar() or Decimal("0.00")

        if balance != 0:
            assets.append(BalanceSheetItem(
                account_number=account.account_number,
                account_name=account.account_name,
                balance=balance
            ))

    liability_accounts = db.query(Account).filter(
        Account.account_type == "LIABILITY",
        Account.is_active == True
    ).all()

    for account in liability_accounts:
        balance = db.query(
            func.coalesce(func.sum(JournalEntry.credit - JournalEntry.debit), 0)
        ).join(
            JournalEntry.transaction
        ).filter(
            JournalEntry.account_id == account.id,
            Transaction.ledger_id == current_ledger.id,
            Transaction.transaction_date <= as_of_date
        ).scalar() or Decimal("0.00")

        if balance != 0:
            liabilities.append(BalanceSheetItem(
                account_number=account.account_number,
                account_name=account.account_name,
                balance=balance
            ))

    equity_accounts = db.query(Account).filter(
        Account.account_type == "EQUITY",
        Account.is_active == True
    ).all()

    for account in equity_accounts:
        balance = db.query(
            func.coalesce(func.sum(JournalEntry.credit - JournalEntry.debit), 0)
        ).join(
            JournalEntry.transaction
        ).filter(
            JournalEntry.account_id == account.id,
            Transaction.ledger_id == current_ledger.id,
            Transaction.transaction_date <= as_of_date
        ).scalar() or Decimal("0.00")

        if balance != 0:
            equity.append(BalanceSheetItem(
                account_number=account.account_number,
                account_name=account.account_name,
                balance=balance
            ))

    total_assets = sum(item.balance for item in assets)
    total_liabilities = sum(item.balance for item in liabilities)
    total_equity = sum(item.balance for item in equity)

    return BalanceSheet(
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_equity=total_equity
    )


@router.get("/income-statement", response_model=IncomeStatement)
def get_income_statement(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    revenues = []
    expenses = []

    revenue_accounts = db.query(Account).filter(
        Account.account_type == "REVENUE",
        Account.is_active == True
    ).all()

    for account in revenue_accounts:
        amount = db.query(
            func.coalesce(func.sum(JournalEntry.credit - JournalEntry.debit), 0)
        ).join(
            JournalEntry.transaction
        ).filter(
            JournalEntry.account_id == account.id,
            Transaction.ledger_id == current_ledger.id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).scalar() or Decimal("0.00")

        if amount != 0:
            revenues.append(IncomeStatementItem(
                account_number=account.account_number,
                account_name=account.account_name,
                amount=amount
            ))

    expense_accounts = db.query(Account).filter(
        Account.account_type == "EXPENSE",
        Account.is_active == True
    ).all()

    for account in expense_accounts:
        amount = db.query(
            func.coalesce(func.sum(JournalEntry.debit - JournalEntry.credit), 0)
        ).join(
            JournalEntry.transaction
        ).filter(
            JournalEntry.account_id == account.id,
            Transaction.ledger_id == current_ledger.id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        ).scalar() or Decimal("0.00")

        if amount != 0:
            expenses.append(IncomeStatementItem(
                account_number=account.account_number,
                account_name=account.account_name,
                amount=amount
            ))

    total_revenue = sum(item.amount for item in revenues)
    total_expenses = sum(item.amount for item in expenses)
    net_income = total_revenue - total_expenses

    return IncomeStatement(
        revenues=revenues,
        expenses=expenses,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_income=net_income
    )
