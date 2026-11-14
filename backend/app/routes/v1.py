"""
API for other programs, at /api/v1.

Reached with a personal key (Authorization: Bearer pr_...), never with the
app's login, and the key is accepted nowhere else. A key reads. A key made
to write can also book, but only in ledgers where its owner is OWNER or
MEMBER; a VIEWER's ledger stays read-only whatever the key says. Writing is
kept narrow: completing drafts, joining the two halves of a transfer, new
transactions, new accounts and market values. Posted transactions are never changed here; that is done in the app.

Amounts are numbers in the ledger's currency (NOK), signed the way the
account type is normally read: assets and expenses grow with debit,
liabilities, equity and income with credit. Draft transactions from bank sync
are included, as in the app's own reports: they carry the bank side only,
so they move bank balances but not income or expenses until posted.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from backend.database import get_db
from ..models import (
    Account, AccountType, ApiToken, BankAccount, FireRole, JournalEntry, Ledger,
    LedgerMember, LedgerRole, Transaction, TransactionSource, TransactionStatus, User,
)
from ..market_value import set_market_value
from ..transaction_chaining import TransactionChainMatcher
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


WRITING_ROLES = {LedgerRole.OWNER, LedgerRole.MEMBER}


def _can_write(token: ApiToken, role: LedgerRole) -> bool:
    return bool(token.can_write) and role in WRITING_ROLES


def _pick_ledger(db: Session, token: ApiToken, ledger_id: Optional[int]):
    readable = _readable_ledgers(db, token)
    if ledger_id is None:
        if len(readable) == 1:
            return readable[0]
        if not readable:
            raise HTTPException(status_code=404, detail="Nøkkelen har ikke tilgang til noe regnskap")
        raise HTTPException(
            status_code=400,
            detail="Velg regnskap med ?ledger_id=. Se GET /api/v1/ledgers.",
        )
    for ledger, role in readable:
        if ledger.id == ledger_id:
            return ledger, role
    raise HTTPException(status_code=404, detail="Fant ikke regnskapet")


def get_ledger(
    ledger_id: Optional[int] = Query(None, description="Required when the key can read more than one ledger"),
    token: ApiToken = Depends(get_api_token),
    db: Session = Depends(get_db),
) -> Ledger:
    return _pick_ledger(db, token, ledger_id)[0]


def get_writable_ledger(
    ledger_id: Optional[int] = Query(None, description="Required when the key can read more than one ledger"),
    token: ApiToken = Depends(get_api_token),
    db: Session = Depends(get_db),
) -> Ledger:
    ledger, role = _pick_ledger(db, token, ledger_id)
    if not token.can_write:
        raise HTTPException(status_code=403, detail="Nøkkelen kan bare lese")
    if role not in WRITING_ROLES:
        raise HTTPException(status_code=403, detail="Du har bare lesetilgang til dette regnskapet")
    return ledger


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
    """The ledgers this key can read, and whether it can write in each."""
    return [
        {"id": ledger.id, "name": ledger.name, "role": role.value, "can_write": _can_write(token, role)}
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
    return [_account_out(a, numbers) for a in accounts]


def _account_out(a: Account, numbers: dict) -> dict:
    return {
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

def _transaction_out(t: Transaction) -> dict:
    return {
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
        "transactions": [_transaction_out(t) for t in transactions],
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


# ─── Writing ─────────────────────────────────────────────────────────────────

CENT = Decimal("0.01")


class LineIn(BaseModel):
    """One journal line. Name the account by id or by number."""
    account_id: Optional[int] = None
    account_number: Optional[str] = None
    debit: Decimal = Field(default=Decimal(0), ge=0)
    credit: Decimal = Field(default=Decimal(0), ge=0)
    description: Optional[str] = Field(default=None, max_length=500)


class PostDraftIn(BaseModel):
    # The counter-entries; the bank's own line stays as it is
    lines: List[LineIn] = []
    description: Optional[str] = Field(default=None, min_length=1, max_length=500)


class TransactionIn(BaseModel):
    on: date = Field(alias="date")
    description: str = Field(min_length=1, max_length=500)
    reference: Optional[str] = Field(default=None, max_length=100)
    status: Literal["DRAFT", "POSTED"] = "POSTED"
    lines: List[LineIn] = Field(min_length=2)


class AccountIn(BaseModel):
    number: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    type: AccountType
    parent_number: Optional[str] = None
    description: Optional[str] = None
    fire_role: Optional[FireRole] = None
    fire_unlock_age: Optional[int] = Field(default=None, ge=0, le=100)
    wealth_valuation_percent: Optional[Decimal] = Field(default=None, ge=0, le=100)
    # Where market value changes are booked, for investment accounts
    value_change_account_number: Optional[str] = None


class MarketValueIn(BaseModel):
    value: Decimal
    # Defaults to today
    as_of: Optional[date] = Field(default=None, alias="date")


def _account_by_number(db: Session, ledger: Ledger, number: str) -> Account:
    account = db.query(Account).filter(
        Account.ledger_id == ledger.id, Account.account_number == number
    ).first()
    if not account:
        raise HTTPException(status_code=400, detail=f"Fant ikke konto {number}")
    return account


def _journal_lines(db: Session, ledger: Ledger, lines: List[LineIn]) -> List[JournalEntry]:
    entries = []
    for i, line in enumerate(lines, start=1):
        debit = line.debit.quantize(CENT)
        credit = line.credit.quantize(CENT)
        if (debit > 0) == (credit > 0):
            raise HTTPException(
                status_code=400,
                detail=f"Linje {i}: oppgi enten debit eller credit, større enn null",
            )
        if line.account_id is not None:
            account = db.query(Account).filter(
                Account.id == line.account_id, Account.ledger_id == ledger.id
            ).first()
            if not account:
                raise HTTPException(status_code=400, detail=f"Linje {i}: fant ikke konto-id {line.account_id}")
            if line.account_number and line.account_number != account.account_number:
                raise HTTPException(status_code=400, detail=f"Linje {i}: account_id og account_number er ulike kontoer")
        elif line.account_number:
            account = _account_by_number(db, ledger, line.account_number)
        else:
            raise HTTPException(status_code=400, detail=f"Linje {i}: mangler konto")
        if not account.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Linje {i}: konto {account.account_number} er deaktivert",
            )
        entries.append(JournalEntry(
            account_id=account.id, debit=debit, credit=credit, description=line.description,
        ))
    return entries


def _check_balanced(entries) -> None:
    if len(entries) < 2:
        raise HTTPException(status_code=400, detail="Et bilag trenger minst to linjer")
    debit = sum((e.debit for e in entries), Decimal(0))
    credit = sum((e.credit for e in entries), Decimal(0))
    if debit != credit:
        raise HTTPException(
            status_code=400,
            detail=f"Bilaget balanserer ikke: debit {debit}, credit {credit}",
        )


def _load_transaction(db: Session, ledger: Ledger, transaction_id: int) -> Transaction:
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id, Transaction.ledger_id == ledger.id
    ).with_for_update().first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Fant ikke bilaget")
    return transaction


@router.post("/transactions/{transaction_id}/post")
def post_draft(
    transaction_id: int,
    payload: PostDraftIn,
    ledger: Ledger = Depends(get_writable_ledger),
    db: Session = Depends(get_db),
):
    """
    Book a draft: add the counter-entries and mark it posted. The lines it
    already has (from bank sync, the bank side) are kept as they are.
    """
    transaction = _load_transaction(db, ledger, transaction_id)
    if transaction.status != TransactionStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Bilaget er allerede bokført")
    added = _journal_lines(db, ledger, payload.lines)
    _check_balanced(list(transaction.journal_entries) + added)
    for entry in added:
        transaction.journal_entries.append(entry)
    if payload.description:
        transaction.description = payload.description
    transaction.status = TransactionStatus.POSTED
    db.commit()
    db.refresh(transaction)
    return _transaction_out(transaction)


class ChainIn(BaseModel):
    first_id: int
    second_id: int


@router.get("/transactions/chain-suggestions")
def chain_suggestions(ledger: Ledger = Depends(get_ledger), db: Session = Depends(get_db)):
    """
    Pairs of bank drafts that look like the two sides of one transfer between
    the ledger's own accounts: same amount, opposite sides, at most two days apart.
    """
    return [
        {
            "first_id": s.primary_transaction_id,
            "second_id": s.secondary_transaction_id,
            "amount": _num(s.amount),
            "first_date": s.primary_date.isoformat(),
            "second_date": s.secondary_date.isoformat(),
            "first_description": s.primary_description,
            "second_description": s.secondary_description,
            "first_account": s.primary_account_name,
            "second_account": s.secondary_account_name,
            "confidence": s.confidence,
        }
        for s in TransactionChainMatcher.find_chain_candidates(db, ledger.id)
    ]


@router.post("/transactions/chain")
def chain_drafts(
    payload: ChainIn,
    ledger: Ledger = Depends(get_writable_ledger),
    db: Session = Depends(get_db),
):
    """
    Join two bank drafts, one on each side of a transfer between own accounts,
    into one posted transaction. Both must be drafts with only their bank line,
    on different accounts, and balance each other exactly.
    """
    if payload.first_id == payload.second_id:
        raise HTTPException(status_code=400, detail="Velg to ulike bilag")
    first = _load_transaction(db, ledger, payload.first_id)
    second = _load_transaction(db, ledger, payload.second_id)
    for t in (first, second):
        if t.status != TransactionStatus.DRAFT:
            raise HTTPException(status_code=409, detail=f"Bilag {t.id} er allerede bokført")
        if len(t.journal_entries) != 1:
            raise HTTPException(status_code=400, detail=f"Bilag {t.id} har mer enn banklinjen")
    a, b = first.journal_entries[0], second.journal_entries[0]
    if a.account_id == b.account_id:
        raise HTTPException(status_code=400, detail="Begge bilagene er på samme konto")
    if a.debit - a.credit != b.credit - b.debit:
        raise HTTPException(status_code=400, detail="Beløpene går ikke opp mot hverandre")
    # The earlier one is kept, as in the app
    keep, drop = (first, second) if (first.transaction_date, first.id) <= (second.transaction_date, second.id) else (second, first)
    merged = TransactionChainMatcher.chain_transactions(db, ledger.id, keep.id, drop.id, auto_post=True)
    db.commit()
    return _transaction_out(merged)


@router.post("/transactions", status_code=201)
def create_transaction(
    payload: TransactionIn,
    ledger: Ledger = Depends(get_writable_ledger),
    token: ApiToken = Depends(get_api_token),
    db: Session = Depends(get_db),
):
    """A new transaction, balanced, as a draft or posted."""
    entries = _journal_lines(db, ledger, payload.lines)
    _check_balanced(entries)
    transaction = Transaction(
        ledger_id=ledger.id,
        created_by=token.user_id,
        transaction_date=payload.on,
        description=payload.description,
        reference=payload.reference,
        status=TransactionStatus[payload.status],
        source=TransactionSource.API,
        is_reconciled=False,
        journal_entries=entries,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return _transaction_out(transaction)


@router.delete("/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    ledger: Ledger = Depends(get_writable_ledger),
    db: Session = Depends(get_db),
):
    """Delete a draft this API made. Anything else is removed in the app."""
    transaction = _load_transaction(db, ledger, transaction_id)
    if transaction.source != TransactionSource.API or transaction.status != TransactionStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail="Bare kladder laget via API-et kan slettes her",
        )
    db.delete(transaction)
    db.commit()
    return {"deleted": transaction_id}


@router.post("/accounts", status_code=201)
def create_account(
    payload: AccountIn,
    ledger: Ledger = Depends(get_writable_ledger),
    db: Session = Depends(get_db),
):
    """A new account in the chart of accounts."""
    exists = db.query(Account.id).filter(
        Account.ledger_id == ledger.id, Account.account_number == payload.number
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail=f"Konto {payload.number} finnes allerede")
    parent = _account_by_number(db, ledger, payload.parent_number) if payload.parent_number else None
    value_change = (
        _account_by_number(db, ledger, payload.value_change_account_number)
        if payload.value_change_account_number else None
    )
    account = Account(
        ledger_id=ledger.id,
        account_number=payload.number,
        account_name=payload.name,
        account_type=payload.type,
        parent_account_id=parent.id if parent else None,
        value_change_account_id=value_change.id if value_change else None,
        fire_role=payload.fire_role,
        fire_unlock_age=payload.fire_unlock_age,
        wealth_valuation_percent=payload.wealth_valuation_percent,
        description=payload.description,
        is_active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _account_out(account, {parent.id: parent.account_number} if parent else {})


@router.post("/accounts/{account_id}/market-value")
def record_market_value(
    account_id: int,
    payload: MarketValueIn,
    ledger: Ledger = Depends(get_writable_ledger),
    token: ApiToken = Depends(get_api_token),
    db: Session = Depends(get_db),
):
    """
    Bring an investment account to its market value on a date (default
    today). The difference is booked against the account's value change
    account. Values must be entered in date order; the same date again
    replaces the earlier one.
    """
    account = db.query(Account).filter(
        Account.id == account_id, Account.ledger_id == ledger.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Fant ikke kontoen")
    adjustment = set_market_value(
        db, ledger.id, account, payload.value, payload.as_of or date.today(), created_by=token.user_id,
    )
    db.commit()
    if adjustment:
        db.refresh(adjustment)
    return {"adjustment": _transaction_out(adjustment) if adjustment else None}
