from datetime import date
from decimal import Decimal
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from ..models import (
    Account,
    AccountType,
    Ledger,
    LedgerMember,
    LedgerRole,
    SettlementExcludedAccount,
    SettlementFixedPayment,
    SettlementMember,
    SettlementSettings,
    User,
)
from ..schemas import SettlementCalculation, SettlementSettingsOut, SettlementSettingsUpdate
from ..settlement_engine import SettlementDisabled, calculate_settlement
from ..auth import get_current_active_user, get_current_ledger, get_user_role_in_ledger

router = APIRouter(prefix="/settlement", tags=["settlement"])

SHARE_TOLERANCE = Decimal("0.01")


def _load_settings(db: Session, ledger_id: int) -> SettlementSettings | None:
    return (
        db.query(SettlementSettings)
        .options(
            joinedload(SettlementSettings.members).joinedload(SettlementMember.user),
            joinedload(SettlementSettings.excluded_accounts),
            joinedload(SettlementSettings.fixed_payments),
        )
        .filter(SettlementSettings.ledger_id == ledger_id)
        .first()
    )


def _to_out(ledger_id: int, settings: SettlementSettings | None) -> SettlementSettingsOut:
    if settings is None:
        return SettlementSettingsOut(
            ledger_id=ledger_id,
            is_enabled=False,
            operating_account_id=None,
            variable_lookback_months=3,
            carry_start=None,
            card_due_day=15,
            members=[],
            excluded_account_ids=[],
            updated_at=None,
        )
    return SettlementSettingsOut(
        ledger_id=ledger_id,
        is_enabled=settings.is_enabled,
        operating_account_id=settings.operating_account_id,
        variable_lookback_months=settings.variable_lookback_months,
        carry_start=settings.carry_start,
        card_due_day=settings.card_due_day,
        members=[
            {
                "user_id": m.user_id,
                "full_name": m.user.full_name,
                "email": m.user.email,
                "share_percent": m.share_percent,
                "deposit_account_id": m.deposit_account_id,
            }
            for m in sorted(settings.members, key=lambda m: m.user_id)
        ],
        excluded_account_ids=sorted(e.account_id for e in settings.excluded_accounts),
        fixed_payments=[
            {
                "id": fp.id,
                "name": fp.name,
                "account_id": fp.account_id,
                "paid_from_account_id": fp.paid_from_account_id,
                "due_day": fp.due_day,
                "amount": fp.amount,
                "first_month": fp.first_month,
                "first_amount": fp.first_amount,
                "payment_count": fp.payment_count,
            }
            for fp in sorted(settings.fixed_payments, key=lambda fp: (fp.due_day, fp.id))
        ],
        updated_at=settings.updated_at,
    )


@router.get("/settings", response_model=SettlementSettingsOut)
def get_settlement_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    """Settlement configuration for the current ledger (defaults if never configured)"""
    return _to_out(current_ledger.id, _load_settings(db, current_ledger.id))


@router.put("/settings", response_model=SettlementSettingsOut)
def update_settlement_settings(
    payload: SettlementSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    """Replace settlement configuration for the current ledger (owner only)"""
    if get_user_role_in_ledger(db, current_user.id, current_ledger.id) != LedgerRole.OWNER:
        raise HTTPException(status_code=403, detail="Kun eier av regnskapet kan endre avregningsinnstillinger")

    _validate(db, current_ledger.id, payload)

    settings = _load_settings(db, current_ledger.id)
    if settings is None:
        settings = SettlementSettings(ledger_id=current_ledger.id)
        db.add(settings)

    settings.is_enabled = payload.is_enabled
    settings.operating_account_id = payload.operating_account_id
    settings.variable_lookback_months = payload.variable_lookback_months
    settings.carry_start = payload.carry_start
    settings.card_due_day = payload.card_due_day

    # Delete old rows before inserting replacements so the unique
    # (settings_id, user_id) key is not hit mid-flush
    settings.members.clear()
    settings.excluded_accounts.clear()
    db.flush()

    settings.members = [
        SettlementMember(
            user_id=m.user_id,
            share_percent=m.share_percent,
            deposit_account_id=m.deposit_account_id,
        )
        for m in payload.members
    ]
    settings.excluded_accounts = [
        SettlementExcludedAccount(account_id=account_id)
        for account_id in sorted(set(payload.excluded_account_ids))
    ]
    if payload.fixed_payments is not None:
        settings.fixed_payments = [
            SettlementFixedPayment(
                name=fp.name.strip(),
                account_id=fp.account_id,
                paid_from_account_id=fp.paid_from_account_id,
                due_day=fp.due_day,
                amount=fp.amount,
                first_month=fp.first_month.replace(day=1),
                first_amount=fp.first_amount,
                payment_count=fp.payment_count,
            )
            for fp in payload.fixed_payments
        ]

    db.commit()
    return _to_out(current_ledger.id, _load_settings(db, current_ledger.id))


def _validate(db: Session, ledger_id: int, payload: SettlementSettingsUpdate) -> None:
    if not 1 <= payload.card_due_day <= 28:
        raise HTTPException(status_code=400, detail="Forfallsdag må være mellom 1 og 28")
    if not 1 <= payload.variable_lookback_months <= 24:
        raise HTTPException(status_code=400, detail="Historikk for variable kostnader må være 1–24 måneder")

    ledger_user_ids = {
        m.user_id for m in db.query(LedgerMember).filter(LedgerMember.ledger_id == ledger_id).all()
    }
    seen = set()
    for m in payload.members:
        if m.user_id not in ledger_user_ids:
            raise HTTPException(status_code=400, detail=f"Bruker {m.user_id} er ikke medlem av regnskapet")
        if m.user_id in seen:
            raise HTTPException(status_code=400, detail="Samme bruker er oppført flere ganger")
        seen.add(m.user_id)
        if m.share_percent < 0 or m.share_percent > 100:
            raise HTTPException(status_code=400, detail="Andel må være mellom 0 og 100 prosent")

    fixed = payload.fixed_payments or []
    loan_accounts = [fp.account_id for fp in fixed]
    if len(set(loan_accounts)) != len(loan_accounts):
        raise HTTPException(status_code=400, detail="Et lån kan bare ha én fast avtale")
    for fp in fixed:
        if not fp.name.strip():
            raise HTTPException(status_code=400, detail="Faste avtaler må ha et navn")
        if not 1 <= fp.due_day <= 31:
            raise HTTPException(status_code=400, detail="Trekkdag må være mellom 1 og 31")
        if fp.amount <= 0 or (fp.first_amount is not None and fp.first_amount <= 0):
            raise HTTPException(status_code=400, detail="Beløpet for en fast avtale må være positivt")
        if fp.payment_count is not None and fp.payment_count < 1:
            raise HTTPException(status_code=400, detail="Antall terminer må være minst 1")

    account_ids = {payload.operating_account_id} | set(payload.excluded_account_ids) | {
        m.deposit_account_id for m in payload.members
    } | set(loan_accounts) | {fp.paid_from_account_id for fp in fixed}
    account_ids.discard(None)
    if account_ids:
        accounts = {
            a.id: a for a in db.query(Account).filter(
                Account.ledger_id == ledger_id, Account.id.in_(account_ids)
            ).all()
        }
        missing = account_ids - accounts.keys()
        if missing:
            raise HTTPException(status_code=400, detail="En eller flere kontoer tilhører ikke regnskapet")

        if payload.operating_account_id is not None:
            if accounts[payload.operating_account_id].account_type != AccountType.ASSET:
                raise HTTPException(status_code=400, detail="Driftskontoen må være en eiendelskonto (bank)")
        for account_id in payload.excluded_account_ids:
            if accounts[account_id].account_type != AccountType.EXPENSE:
                raise HTTPException(status_code=400, detail="Kun kostnadskontoer kan ekskluderes")
        for fp in fixed:
            if accounts[fp.account_id].account_type != AccountType.LIABILITY:
                raise HTTPException(status_code=400, detail=f"{fp.name}: lånekontoen må være en gjeldskonto")
            if fp.paid_from_account_id is not None and accounts[fp.paid_from_account_id].account_type != AccountType.ASSET:
                raise HTTPException(status_code=400, detail=f"{fp.name}: kontoen det trekkes fra må være en bankkonto")

    # A disabled configuration may be incomplete; an enabled one must be usable
    if payload.is_enabled:
        if payload.operating_account_id is None:
            raise HTTPException(status_code=400, detail="Driftskonto må velges før avregning kan aktiveres")
        if not payload.members:
            raise HTTPException(status_code=400, detail="Minst én deltaker må være satt opp")
        total = sum((m.share_percent for m in payload.members), Decimal("0"))
        if abs(total - Decimal("100")) > SHARE_TOLERANCE:
            raise HTTPException(status_code=400, detail=f"Andelene må summere til 100 % (nå {total} %)")


@router.get("/calculation", response_model=SettlementCalculation)
def get_settlement_calculation(
    month: str | None = Query(None, description="YYYY-MM, standard er inneværende måned"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    """Forecast and per-member split of shared expenses for a month"""
    today = date.today()
    if month is None:
        year, mon = today.year, today.month
    else:
        m = re.fullmatch(r"(\d{4})-(\d{2})", month)
        if not m or not 1 <= int(m.group(2)) <= 12:
            raise HTTPException(status_code=400, detail="Måned må angis som YYYY-MM")
        year, mon = int(m.group(1)), int(m.group(2))

    settings = _load_settings(db, current_ledger.id)
    if settings is None or not settings.is_enabled:
        raise HTTPException(status_code=409, detail="Månedsavregning er ikke aktivert for dette regnskapet")

    try:
        return calculate_settlement(db, settings, year, mon, as_of=today)
    except SettlementDisabled:
        raise HTTPException(status_code=409, detail="Månedsavregning er ikke aktivert for dette regnskapet")
