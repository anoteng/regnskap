"""
Read-only API for other programs, at /api/v1.

Reached with a personal key (Authorization: Bearer pr_...), never with the
app's login, and the key is accepted nowhere else. Every route here is a GET,
so a key can read and nothing more.

Amounts are numbers in the ledger's currency (NOK), signed the way the
account type is normally read: assets and expenses grow with debit,
liabilities, equity and income with credit. Draft transactions from bank sync
are included, as in the app's own reports: they carry the bank side only,
so they move bank balances but not income or expenses until posted.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from backend.database import get_db
from ..models import (
    Account, AccountType, ApiToken, BankAccount, JournalEntry, Ledger,
    LedgerMember, Transaction, TransactionStatus, User,
)
from .api_tokens import TOKEN_PREFIX, hash_token

router = APIRouter(prefix="/v1", tags=["api-v1"])

bearer = HTTPBearer(auto_error=False)

DEBIT_NORMAL = {AccountType.ASSET, AccountType.EXPENSE}
BALANCE_TYPES = {AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY}
MAX_MONTHS = 240
LAST_USED_GRANULARITY = timedelta(minutes=5)


def _unauthorized(detail: str):
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_api_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> ApiToken:
    if not credentials or not credentials.credentials.startswith(TOKEN_PREFIX):
        raise _unauthorized("Mangler API-nøkkel")
    token = db.query(ApiToken).filter(
        ApiToken.token_hash == hash_token(credentials.credentials),
        ApiToken.revoked_at.is_(None),
    ).first()
    now = datetime.utcnow()
    if not token or (token.expires_at and token.expires_at <= now):
        raise _unauthorized("Ugyldig eller utløpt API-nøkkel")
    user = db.query(User).filter(User.id == token.user_id, User.is_active == True).first()
    if not user:
        raise _unauthorized("Brukeren er deaktivert")
    # Written now and then, not on every request
    if not token.last_used_at or now - token.last_used_at > LAST_USED_GRANULARITY:
        token.last_used_at = now
        db.commit()
    return token


def _readable_ledgers(db: Session, token: ApiToken):
    """Ledgers the key may read: the user's own memberships, narrowed by the key."""
    query = db.query(Ledger, LedgerMember.role).join(
        LedgerMember, LedgerMember.ledger_id == Ledger.id
    ).filter(
        LedgerMember.user_id == token.user_id,
        Ledger.is_active == True,
    )
    if token.ledger_id is not None:
        query = query.filter(Ledger.id == token.ledger_id)
    return query.order_by(Ledger.id).all()


def get_ledger(
    ledger_id: Optional[int] = Query(None, description="Required when the key can read more than one ledger"),
    token: ApiToken = Depends(get_api_token),
    db: Session = Depends(get_db),
) -> Ledger:
    readable = _readable_ledgers(db, token)
    if ledger_id is None:
        if len(readable) == 1:
            return readable[0][0]
        if not readable:
            raise HTTPException(status_code=404, detail="Nøkkelen har ikke tilgang til noe regnskap")
        raise HTTPException(
            status_code=400,
            detail="Velg regnskap med ?ledger_id=. Se GET /api/v1/ledgers.",
        )
    for ledger, _ in readable:
        if ledger.id == ledger_id:
            return ledger
    raise HTTPException(status_code=404, detail="Fant ikke regnskapet")


def _num(value) -> float:
    return float(Decimal(value or 0).quantize(Decimal("0.01")))


def _signed(account_type: AccountType, debit, credit) -> Decimal:
    debit = Decimal(debit or 0)
    credit = Decimal(credit or 0)
    return debit - credit if account_type in DEBIT_NORMAL else credit - debit


def _parse_month(value: str, name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{name} må være på formen ÅÅÅÅ-MM")


def _month_range(start: date, end: date):
    months = []
    current = start
    while current <= end:
        months.append(current)
        current = date(current.year + current.month // 12, current.month % 12 + 1, 1)
    return months


def _month_window(from_month: Optional[str], to_month: Optional[str]):
    today = date.today()
    end = _parse_month(to_month, "to") if to_month else today.replace(day=1)
    start = _parse_month(from_month, "from") if from_month else date(end.year - 1, end.month, 1)
    if start > end:
        raise HTTPException(status_code=400, detail="from kan ikke være etter to")
    months = _month_range(start, end)
    if len(months) > MAX_MONTHS:
        raise HTTPException(status_code=400, detail=f"Høyst {MAX_MONTHS} måneder per kall")
    return months


# ─── Ledgers and accounts ────────────────────────────────────────────────────

@router.get("/ledgers")
def list_ledgers(token: ApiToken = Depends(get_api_token), db: Session = Depends(get_db)):
    """The ledgers this key can read."""
    return [
        {"id": ledger.id, "name": ledger.name, "role": role.value}
        for ledger, role in _readable_ledgers(db, token)
    ]


@router.get("/accounts")
def list_accounts(
    include_inactive: bool = False,
    ledger: Ledger = Depends(get_ledger),
    db: Session = Depends(get_db),
):
    """
    The chart of accounts. Income (REVENUE) and expense (EXPENSE) accounts
    are the categories; the ledger has no separate category list in use.
    """
    query = db.query(Account).filter(Account.ledger_id == ledger.id)
    if not include_inactive:
        query = query.filter(Account.is_active == True)
    accounts = query.order_by(Account.account_number).all()
    numbers = {a.id: a.account_number for a in accounts}
    return [
        {
            "id": a.id,
            "number": a.account_number,
            "name": a.account_name,
            "type": a.account_type.value,
            "parent_id": a.parent_account_id,
            "parent_number": numbers.get(a.parent_account_id),
            "description": a.description,
            "is_active": a.is_active,
            "fire_role": a.fire_role.value if a.fire_role else None,
            "fire_unlock_age": a.fire_unlock_age,
            "wealth_valuation_percent": _num(a.wealth_valuation_percent)
            if a.wealth_valuation_percent is not None else None,
        }
        for a in accounts
    ]


@router.get("/bank-accounts")
def list_bank_accounts(ledger: Ledger = Depends(get_ledger), db: Session = Depends(get_db)):
    """Bank accounts and cards, with today's balance from the ledger."""
    rows = db.query(BankAccount, Account).join(
        Account, Account.id == BankAccount.account_id
    ).filter(BankAccount.ledger_id == ledger.id).order_by(BankAccount.id).all()

    sums = dict(
        (account_id, (debit, credit))
        for account_id, debit, credit in db.query(
            JournalEntry.account_id, func.sum(JournalEntry.debit), func.sum(JournalEntry.credit)
        ).join(Transaction).filter(
            Transaction.ledger_id == ledger.id,
            Transaction.transaction_date <= date.today(),
            JournalEntry.account_id.in_([account.id for _, account in rows] or [0]),
        ).group_by(JournalEntry.account_id).all()
    )
    return [
        {
            "id": bank.id,
            "name": bank.name,
            "type": bank.account_type.value,
            "bank_account_number": bank.account_number,
            "account_id": account.id,
            "account_number": account.account_number,
            "is_active": bank.is_active,
            "balance": _num(_signed(account.account_type, *sums.get(account.id, (0, 0)))),
        }
        for bank, account in rows
    ]


# ─── Transactions ────────────────────────────────────────────────────────────

@router.get("/transactions")
def list_transactions(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    account_id: Optional[int] = None,
    account_number: Optional[str] = None,
    status: Optional[TransactionStatus] = None,
    limit: int = Query(500, ge=1, le=1000),
    cursor: Optional[str] = Query(None, description="next_cursor from the previous page"),
    ledger: Ledger = Depends(get_ledger),
    db: Session = Depends(get_db),
):
    """Transactions with all their lines, oldest first, a page at a time."""
    query = db.query(Transaction).filter(Transaction.ledger_id == ledger.id)
    if from_date:
        query = query.filter(Transaction.transaction_date >= from_date)
    if to_date:
        query = query.filter(Transaction.transaction_date <= to_date)
    if status:
        query = query.filter(Transaction.status == status)
    if account_id is not None or account_number:
        account_query = db.query(Account.id).filter(Account.ledger_id == ledger.id)
        if account_id is not None:
            account_query = account_query.filter(Account.id == account_id)
        if account_number:
            account_query = account_query.filter(Account.account_number == account_number)
        query = query.filter(Transaction.journal_entries.any(JournalEntry.account_id.in_(account_query)))
    if cursor:
        try:
            cursor_date, cursor_id = cursor.split("_")
            cursor_date = date.fromisoformat(cursor_date)
            cursor_id = int(cursor_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Ugyldig cursor")
        query = query.filter(or_(
            Transaction.transaction_date > cursor_date,
            and_(Transaction.transaction_date == cursor_date, Transaction.id > cursor_id),
        ))

    transactions = query.options(
        selectinload(Transaction.journal_entries).selectinload(JournalEntry.account)
    ).order_by(Transaction.transaction_date, Transaction.id).limit(limit + 1).all()

    has_more = len(transactions) > limit
    transactions = transactions[:limit]
    last = transactions[-1] if transactions else None
    return {
        "transactions": [
            {
                "id": t.id,
                "date": t.transaction_date.isoformat(),
                "description": t.description,
                "reference": t.reference,
                "status": t.status.value,
                "source": t.source.value if t.source else None,
                "lines": [
                    {
                        "account_id": je.account_id,
                        "account_number": je.account.account_number,
                        "account_name": je.account.account_name,
                        "account_type": je.account.account_type.value,
                        "debit": _num(je.debit),
                        "credit": _num(je.credit),
                        "description": je.description,
                    }
                    for je in t.journal_entries
                ],
            }
            for t in transactions
        ],
        "next_cursor": f"{last.transaction_date.isoformat()}_{last.id}" if has_more else None,
    }


# ─── Monthly figures ─────────────────────────────────────────────────────────

def _monthly(db: Session, ledger: Ledger, months):
    """Per account: balance before the first month, and movement in each month."""
    start = months[0]
    last = months[-1]
    end_exclusive = date(last.year + last.month // 12, last.month % 12 + 1, 1)

    accounts = {a.id: a for a in db.query(Account).filter(Account.ledger_id == ledger.id).all()}

    opening = defaultdict(Decimal)
    for account_id, debit, credit in db.query(
        JournalEntry.account_id, func.sum(JournalEntry.debit), func.sum(JournalEntry.credit)
    ).join(Transaction).filter(
        Transaction.ledger_id == ledger.id,
        Transaction.transaction_date < start,
    ).group_by(JournalEntry.account_id).all():
        account = accounts.get(account_id)
        if account and account.account_type in BALANCE_TYPES:
            opening[account_id] = _signed(account.account_type, debit, credit)

    year = func.year(Transaction.transaction_date)
    month = func.month(Transaction.transaction_date)
    movement = defaultdict(Decimal)
    for account_id, y, m, debit, credit in db.query(
        JournalEntry.account_id, year, month, func.sum(JournalEntry.debit), func.sum(JournalEntry.credit)
    ).join(Transaction).filter(
        Transaction.ledger_id == ledger.id,
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end_exclusive,
    ).group_by(JournalEntry.account_id, year, month).all():
        account = accounts.get(account_id)
        if account:
            movement[(account_id, date(int(y), int(m), 1))] = _signed(account.account_type, debit, credit)

    return accounts, opening, movement


@router.get("/balances/monthly")
def monthly_balances(
    from_month: Optional[str] = Query(None, alias="from", description="ÅÅÅÅ-MM, default 12 months before to"),
    to_month: Optional[str] = Query(None, alias="to", description="ÅÅÅÅ-MM, default this month"),
    ledger: Ledger = Depends(get_ledger),
    db: Session = Depends(get_db),
):
    """
    Per month and account: movement in the month, and for balance accounts
    (ASSET, LIABILITY, EQUITY) the balance at the end of it. Accounts with
    neither are left out.
    """
    months = _month_window(from_month, to_month)
    accounts, opening, movement = _monthly(db, ledger, months)

    running = dict(opening)
    result = []
    for m in months:
        rows = []
        for account_id, account in sorted(accounts.items(), key=lambda item: item[1].account_number):
            moved = movement.get((account_id, m), Decimal(0))
            row = {
                "account_id": account_id,
                "account_number": account.account_number,
                "account_name": account.account_name,
                "type": account.account_type.value,
                "movement": _num(moved),
            }
            if account.account_type in BALANCE_TYPES:
                running[account_id] = running.get(account_id, Decimal(0)) + moved
                row["balance"] = _num(running[account_id])
                if moved == 0 and running[account_id] == 0:
                    continue
            elif moved == 0:
                continue
            rows.append(row)
        result.append({"month": m.strftime("%Y-%m"), "accounts": rows})
    return {"ledger_id": ledger.id, "months": result}


@router.get("/summary/monthly")
def monthly_summary(
    from_month: Optional[str] = Query(None, alias="from", description="ÅÅÅÅ-MM, default 12 months before to"),
    to_month: Optional[str] = Query(None, alias="to", description="ÅÅÅÅ-MM, default this month"),
    ledger: Ledger = Depends(get_ledger),
    db: Session = Depends(get_db),
):
    """
    Income, expenses and net per month, and assets, liabilities and net
    worth at the end of each month. Moving money between your own accounts
    is neither income nor expense.
    """
    months = _month_window(from_month, to_month)
    accounts, opening, movement = _monthly(db, ledger, months)

    assets = sum((v for k, v in opening.items() if accounts[k].account_type == AccountType.ASSET), Decimal(0))
    liabilities = sum((v for k, v in opening.items() if accounts[k].account_type == AccountType.LIABILITY), Decimal(0))

    result = []
    for m in months:
        income = expenses = Decimal(0)
        for (account_id, month), moved in movement.items():
            if month != m:
                continue
            kind = accounts[account_id].account_type
            if kind == AccountType.REVENUE:
                income += moved
            elif kind == AccountType.EXPENSE:
                expenses += moved
            elif kind == AccountType.ASSET:
                assets += moved
            elif kind == AccountType.LIABILITY:
                liabilities += moved
        result.append({
            "month": m.strftime("%Y-%m"),
            "income": _num(income),
            "expenses": _num(expenses),
            "net": _num(income - expenses),
            "assets": _num(assets),
            "liabilities": _num(liabilities),
            "net_worth": _num(assets - liabilities),
        })
    return {"ledger_id": ledger.id, "months": result}
