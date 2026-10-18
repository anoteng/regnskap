"""FIRE endpoints: assumptions in, a dated answer out.

The settings row is created on first save, so a ledger that has never opened
this view carries no baggage. Everything else — capital, spending, income —
is read from the ledger at calculation time, which keeps the numbers honest
as the bookkeeping moves on.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from ..models import (
    Account,
    AccountType,
    FireExcludedAccount,
    FireIncomeStream,
    FireObligation,
    FireObligationKind,
    FireSettings,
    Ledger,
    LedgerMember,
    User,
)
from ..schemas import (
    FireAssumptions,
    FireBucket,
    FireChart,
    FireChartPoint,
    FireCostAccount,
    FireIncomeStreamInput,
    FireIncomeStreamOut,
    FireNumberOut,
    FireObligationInput,
    FireObligationOut,
    FireObligationOutcome,
    FireProjectionOut,
    FireResult,
    FireSettingsOut,
    FireSettingsUpdate,
    FireYearRow,
)
from ..auth import get_current_active_user, get_current_ledger
from ..fire_engine import (
    MONTHS_PER_YEAR,
    ConstantReturns,
    FireDisabled,
    age_on,
    build_inputs,
    earliest_retirement,
    fire_number,
    months_between,
    project,
)

router = APIRouter(prefix="/fire", tags=["fire"])

# Retiring later than this is not a plan anyone is making
LATEST_RETIREMENT_AGE = 75


def _load(db: Session, ledger_id: int) -> Optional[FireSettings]:
    return (
        db.query(FireSettings)
        .options(
            joinedload(FireSettings.obligations),
            joinedload(FireSettings.excluded_accounts),
            joinedload(FireSettings.income_streams),
        )
        .filter(FireSettings.ledger_id == ledger_id)
        .first()
    )


def _to_out(ledger_id: int, settings: Optional[FireSettings]) -> FireSettingsOut:
    if settings is None:
        return FireSettingsOut(ledger_id=ledger_id)
    return FireSettingsOut(
        ledger_id=ledger_id,
        is_enabled=settings.is_enabled,
        birth_date=settings.birth_date,
        horizon_age=settings.horizon_age,
        target_retirement_date=settings.target_retirement_date,
        swr_percent=settings.swr_percent,
        inflation_percent=settings.inflation_percent,
        expected_return_percent=settings.expected_return_percent,
        return_volatility_percent=settings.return_volatility_percent,
        inflation_volatility_percent=settings.inflation_volatility_percent,
        lookback_months=settings.lookback_months,
        shared_ledger_id=settings.shared_ledger_id,
        shared_share_percent=settings.shared_share_percent,
        wealth_tax_threshold=settings.wealth_tax_threshold,
        wealth_tax_rate_percent=settings.wealth_tax_rate_percent,
        wealth_tax_step2_threshold=settings.wealth_tax_step2_threshold,
        wealth_tax_step2_rate_percent=settings.wealth_tax_step2_rate_percent,
        wealth_tax_index_threshold=settings.wealth_tax_index_threshold,
        excluded_account_ids=sorted(e.account_id for e in settings.excluded_accounts),
        obligations=[FireObligationOut.model_validate(ob) for ob in settings.obligations],
        income_streams=[
            FireIncomeStreamOut.model_validate(st) for st in settings.income_streams
        ],
        updated_at=settings.updated_at,
    )


@router.get("/settings", response_model=FireSettingsOut)
def get_fire_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    """Assumptions for the current ledger, or the defaults if never saved."""
    return _to_out(current_ledger.id, _load(db, current_ledger.id))


@router.put("/settings", response_model=FireSettingsOut)
def update_fire_settings(
    payload: FireSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    """Save the assumptions. Obligations are managed on their own endpoints."""
    if payload.swr_percent <= 0 or payload.swr_percent > 20:
        raise HTTPException(status_code=400, detail="Uttaksraten må være mellom 0 og 20 prosent")
    if payload.horizon_age < 50 or payload.horizon_age > 120:
        raise HTTPException(status_code=400, detail="Horisontalderen må være mellom 50 og 120")
    if payload.shared_ledger_id:
        if payload.shared_ledger_id == current_ledger.id:
            raise HTTPException(status_code=400, detail="Fellesregnskapet kan ikke være dette regnskapet")
        member = db.query(LedgerMember).filter(
            LedgerMember.ledger_id == payload.shared_ledger_id,
            LedgerMember.user_id == current_user.id,
        ).first()
        if not member:
            raise HTTPException(status_code=403, detail="Du har ikke tilgang til det regnskapet")

    settings = _load(db, current_ledger.id)
    if settings is None:
        settings = FireSettings(ledger_id=current_ledger.id)
        db.add(settings)

    for field in (
        "is_enabled", "birth_date", "horizon_age", "target_retirement_date",
        "swr_percent", "inflation_percent", "expected_return_percent",
        "return_volatility_percent", "inflation_volatility_percent",
        "lookback_months", "shared_ledger_id", "shared_share_percent",
        "wealth_tax_threshold", "wealth_tax_rate_percent",
        "wealth_tax_step2_threshold", "wealth_tax_step2_rate_percent",
        "wealth_tax_index_threshold",
    ):
        setattr(settings, field, getattr(payload, field))

    db.flush()
    db.query(FireExcludedAccount).filter(
        FireExcludedAccount.settings_id == settings.id
    ).delete()
    for account_id in set(payload.excluded_account_ids):
        db.add(FireExcludedAccount(settings_id=settings.id, account_id=account_id))

    db.commit()
    return _to_out(current_ledger.id, _load(db, current_ledger.id))


def _require_settings(db: Session, ledger_id: int) -> FireSettings:
    settings = _load(db, ledger_id)
    if settings is None:
        raise HTTPException(status_code=400, detail="Lagre FIRE-innstillingene først")
    return settings


@router.post("/obligations", response_model=FireObligationOut)
def create_obligation(
    payload: FireObligationInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    """Register a cost that ends — a loan, child support, a fixed-term lease."""
    settings = _require_settings(db, current_ledger.id)
    obligation = FireObligation(settings_id=settings.id)
    _apply(obligation, payload)
    db.add(obligation)
    db.commit()
    db.refresh(obligation)
    return FireObligationOut.model_validate(obligation)


@router.put("/obligations/{obligation_id}", response_model=FireObligationOut)
def update_obligation(
    obligation_id: int,
    payload: FireObligationInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    settings = _require_settings(db, current_ledger.id)
    obligation = db.query(FireObligation).filter(
        FireObligation.id == obligation_id,
        FireObligation.settings_id == settings.id,
    ).first()
    if not obligation:
        raise HTTPException(status_code=404, detail="Forpliktelsen finnes ikke")
    _apply(obligation, payload)
    db.commit()
    db.refresh(obligation)
    return FireObligationOut.model_validate(obligation)


@router.delete("/obligations/{obligation_id}")
def delete_obligation(
    obligation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    settings = _require_settings(db, current_ledger.id)
    obligation = db.query(FireObligation).filter(
        FireObligation.id == obligation_id,
        FireObligation.settings_id == settings.id,
    ).first()
    if not obligation:
        raise HTTPException(status_code=404, detail="Forpliktelsen finnes ikke")
    db.delete(obligation)
    db.commit()
    return {"message": "Forpliktelsen er slettet"}


@router.get("/cost-accounts", response_model=List[FireCostAccount])
def list_cost_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    """Expense accounts an obligation may already be booked on.

    The shared ledger is included, and that is the point: a household
    mortgage pays its interest there, not here, and without it the one
    account that causes the double count could not be picked at all.
    """
    settings = _load(db, current_ledger.id)
    ledger_ids = [current_ledger.id]
    if settings and settings.shared_ledger_id:
        ledger_ids.append(settings.shared_ledger_id)

    names = {
        row.id: row.name for row in
        db.query(Ledger).filter(Ledger.id.in_(ledger_ids)).all()
    }
    accounts = db.query(Account).filter(
        Account.ledger_id.in_(ledger_ids),
        Account.account_type == AccountType.EXPENSE,
        Account.is_active.is_(True),
    ).order_by(Account.ledger_id, Account.account_number).all()

    return [
        FireCostAccount(
            id=a.id,
            ledger_id=a.ledger_id,
            ledger_name=names.get(a.ledger_id, ""),
            account_number=a.account_number,
            account_name=a.account_name,
        )
        for a in accounts
    ]


@router.post("/income-streams", response_model=FireIncomeStreamOut)
def create_income_stream(
    payload: FireIncomeStreamInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    """Register a pension paid as income: folketrygd, tjenestepensjon."""
    settings = _require_settings(db, current_ledger.id)
    stream = FireIncomeStream(settings_id=settings.id)
    _apply_stream(stream, payload)
    db.add(stream)
    db.commit()
    db.refresh(stream)
    return FireIncomeStreamOut.model_validate(stream)


@router.put("/income-streams/{stream_id}", response_model=FireIncomeStreamOut)
def update_income_stream(
    stream_id: int,
    payload: FireIncomeStreamInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    settings = _require_settings(db, current_ledger.id)
    stream = db.query(FireIncomeStream).filter(
        FireIncomeStream.id == stream_id,
        FireIncomeStream.settings_id == settings.id,
    ).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Inntektsstrømmen finnes ikke")
    _apply_stream(stream, payload)
    db.commit()
    db.refresh(stream)
    return FireIncomeStreamOut.model_validate(stream)


@router.delete("/income-streams/{stream_id}")
def delete_income_stream(
    stream_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    settings = _require_settings(db, current_ledger.id)
    stream = db.query(FireIncomeStream).filter(
        FireIncomeStream.id == stream_id,
        FireIncomeStream.settings_id == settings.id,
    ).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Inntektsstrømmen finnes ikke")
    db.delete(stream)
    db.commit()
    return {"status": "deleted"}


def _apply_stream(stream: FireIncomeStream, payload: FireIncomeStreamInput) -> None:
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Inntektsstrømmen må ha et navn")
    if payload.monthly_amount is not None and payload.monthly_amount < 0:
        raise HTTPException(status_code=400, detail="Beløpet kan ikke være negativt")
    if payload.end_age is not None and payload.end_age <= payload.start_age:
        raise HTTPException(
            status_code=400,
            detail="Sluttalderen må være høyere enn startalderen",
        )
    stream.name = payload.name.strip()
    stream.monthly_amount = payload.monthly_amount or Decimal("0")
    stream.start_age = payload.start_age
    stream.end_age = payload.end_age
    stream.inflation_adjusted = payload.inflation_adjusted
    stream.is_active = payload.is_active


def _apply(obligation: FireObligation, payload: FireObligationInput) -> None:
    try:
        kind = FireObligationKind(payload.kind)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Ukjent type: {payload.kind}")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Forpliktelsen må ha et navn")
    if payload.monthly_amount is not None and payload.monthly_amount < 0:
        raise HTTPException(status_code=400, detail="Månedsbeløpet kan ikke være negativt")
    if kind == FireObligationKind.LOAN and not payload.end_date and not payload.balance:
        raise HTTPException(
            status_code=400,
            detail="Et lån trenger enten sluttdato eller saldo, ellers tar det aldri slutt",
        )

    obligation.name = payload.name.strip()
    obligation.kind = kind
    obligation.account_id = payload.account_id
    obligation.cost_account_id = payload.cost_account_id
    obligation.monthly_amount = payload.monthly_amount or Decimal("0")
    obligation.balance = payload.balance
    obligation.interest_percent = payload.interest_percent
    obligation.end_date = payload.end_date
    obligation.inflation_adjusted = payload.inflation_adjusted
    obligation.frees_up_cash = payload.frees_up_cash
    obligation.counts_as_debt = payload.counts_as_debt
    obligation.is_active = payload.is_active


@router.get("/projection", response_model=FireResult)
def get_projection(
    retirement_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger),
):
    """The two answers: what is needed, and when it is there.

    `retirement_date` overrides the saved target, so the view can scrub
    through dates without saving anything.
    """
    settings = _require_settings(db, current_ledger.id)
    try:
        inputs = build_inputs(db, settings)
    except FireDisabled as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    returns = ConstantReturns(inputs.nominal_return, inputs.inflation)
    earliest = earliest_retirement(inputs, returns, LATEST_RETIREMENT_AGE)

    chosen = retirement_date or settings.target_retirement_date
    target = None
    if chosen:
        month = max(0, months_between(inputs.start, chosen))
        target = project(inputs, returns, month)

    number = fire_number(inputs)
    available = sum(b.amount for b in inputs.buckets if b.unlock_age is None and not b.excluded)
    locked = sum(b.amount for b in inputs.buckets if b.unlock_age is not None and not b.excluded)
    excluded = sum(b.amount for b in inputs.buckets if b.excluded)
    real_return = (1 + inputs.nominal_return) / (1 + inputs.inflation) - 1

    return FireResult(
        ledger_id=current_ledger.id,
        assumptions=FireAssumptions(
            as_of=inputs.start,
            birth_date=inputs.birth_date,
            age=age_on(inputs.birth_date, inputs.start),
            horizon_age=inputs.horizon_age,
            monthly_spending=_d(inputs.monthly_spending),
            monthly_net_income=_d(inputs.monthly_net_income),
            monthly_obligations=_d(sum(ob.monthly for ob in inputs.obligations)),
            swr_percent=settings.swr_percent,
            inflation_percent=settings.inflation_percent,
            expected_return_percent=settings.expected_return_percent,
            real_return_percent=_d(real_return * 100, "0.01"),
            capital_available=_d(available),
            capital_locked=_d(locked),
            capital_excluded=_d(excluded),
            buckets=[
                FireBucket(
                    name=b.name,
                    amount=_d(b.amount),
                    unlock_age=b.unlock_age,
                    payout_years=b.payout_years,
                    annual_contribution=_d(b.annual_contribution),
                    valuation_percent=_d(b.valuation_percent, "0.01"),
                    excluded=b.excluded,
                )
                for b in inputs.buckets
            ],
        ),
        fire_number=FireNumberOut(
            perpetual_annual_spending=_d(number.perpetual_annual_spending),
            base_capital=_d(number.base_capital),
            pension_capital=_d(number.pension_capital),
            wealth_tax_annual=_d(number.wealth_tax_annual),
            wealth_tax_capital=_d(number.wealth_tax_capital),
            bridge_capital=_d(number.bridge_capital),
            total=_d(number.total),
        ),
        earliest=_projection_out(earliest, inputs) if earliest else None,
        target=_projection_out(target, inputs) if target else None,
        chart=_chart(inputs, returns, settings),
        warnings=list(inputs.warnings),
    )


def _chart(inputs, returns, settings) -> FireChart:
    """The accumulation picture: two capital paths against what a year costs.

    Both paths run to the horizon with the work never stopping, because the
    question the chart answers is when you *could* stop, not what happens
    after you have. The second path adds nothing at all and shows what the
    pots become on returns alone.

    Only spendable capital is plotted. Four per cent of a pension you cannot
    touch for another fifteen years will not pay this year's bills, so
    counting it would move the crossing to a date that does not exist.
    """
    horizon = inputs.horizon_months
    saving = project(inputs, returns, horizon)
    untouched = project(inputs, returns, horizon, growth_only=True)
    swr = float(settings.swr_percent) / 100.0

    by_year = {row.year: row for row in untouched.rows}
    points: list[FireChartPoint] = []
    crossing_year = crossing_age = None

    for row in saving.rows:
        # The first and last rows are part-years. Scaling them up is what
        # makes a cost line comparable with a withdrawal rate, which is
        # annual by definition.
        scale = MONTHS_PER_YEAR / row.months if row.months else 1.0
        cost = (row.spending + row.obligations + row.wealth_tax) * scale
        need = max(0.0, cost - row.pension_income * scale)
        other = by_year.get(row.year)

        if crossing_year is None and need > 0 and row.available * swr >= need:
            crossing_year, crossing_age = row.year, row.age

        points.append(FireChartPoint(
            year=row.year,
            age=row.age,
            capital_saving=_d(row.available),
            capital_no_deposits=_d(other.available if other else 0.0),
            annual_cost=_d(cost),
            annual_need=_d(need),
            pension_income=_d(row.pension_income * scale),
        ))

    return FireChart(
        swr_percent=settings.swr_percent,
        points=points,
        crossing_year=crossing_year,
        crossing_age=crossing_age,
    )


def _projection_out(p, inputs) -> FireProjectionOut:
    return FireProjectionOut(
        retirement_date=p.retirement_date,
        retirement_age=age_on(inputs.birth_date, p.retirement_date),
        success=p.success,
        depleted_date=p.depleted_date,
        bridge_low=_d(p.bridge_low) if p.bridge_low is not None else None,
        bridge_low_date=p.bridge_low_date,
        first_wealth_tax_year=p.first_wealth_tax_year,
        rows=[
            FireYearRow(
                year=r.year, age=r.age,
                available=_d(r.available), locked=_d(r.locked),
                excluded=_d(r.excluded), total=_d(r.total),
                debt=_d(r.debt), net_wealth=_d(r.net_wealth),
                spending=_d(r.spending), obligations=_d(r.obligations),
                wealth_tax=_d(r.wealth_tax), saved=_d(r.saved),
                withdrawn=_d(r.withdrawn), working=r.working,
                pension_income=_d(r.pension_income), months=r.months,
            )
            for r in p.rows
        ],
        obligations=[
            FireObligationOutcome(
                name=o.name, kind=o.kind, monthly=_d(o.monthly), ends=o.ends,
                derived=o.derived, total_interest=_d(o.total_interest),
                frees_up_cash=o.frees_up_cash,
            )
            for o in p.obligations
        ],
    )


def _d(value: float, places: str = "1") -> Decimal:
    """Forecasts are rounded to the krone; pretending to ore would be a lie."""
    return Decimal(str(round(float(value), 2))).quantize(Decimal(places))
