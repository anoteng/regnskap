"""FIRE projection: when the capital covers the spending, and for how long.

Five things make this more than dividing a pile of money by four percent:

  * **Locked capital.** Pension savings cannot pay for the years before they
    unlock. Retiring at 45 with most of the money tied up until 67 means the
    available pot alone has to carry twenty-two years. The simulation keeps
    the pots apart and only merges one in when its age arrives.

  * **Costs that stop.** A mortgage runs out, a student loan runs out, child
    support ends on a birthday. Treating them as permanent spending overstates
    what is needed for life; ignoring them understates what is needed for the
    years they still run. They are carried as dated obligations and amortised.

  * **Wealth tax.** It is charged on net wealth, so paying off debt brings it
    closer, and it is funded out of the same capital it is charged on. Which
    pot a krone is drawn from therefore matters: bank deposits count at full
    value, share savings at eighty per cent, pension capital at nothing, so
    withdrawals take the most heavily taxed money first and leave the rest
    compounding. See `_draw_order`.

  * **Pensions.** Folketrygd and a tjenestepensjon are not capital at all —
    they are an income that starts on a birthday — while IPS and a
    pensjonskapitalbevis are capital that cannot be emptied at will but is
    paid out over a fixed number of years. Both reduce what the capital has
    to raise, neither can be spent early, and treating either as an ordinary
    pot would answer the wrong question.

Everything runs in today's kroner. Spending then stays flat, growth is the
real return, and a nominal loan payment shrinks year by year the way it
actually does. The one place nominal amounts survive is loan balances, which
amortise on their own terms and are deflated when needed.

Unlike the rest of the application this module computes in float rather than
Decimal. It is a forecast, not a ledger: nothing here is booked, the inputs
are assumptions to one decimal place, and a Monte Carlo pass will run this
loop tens of thousands of times.

The Monte Carlo seam is `ReturnModel`. The deterministic projection feeds in
a constant; sampling variable returns needs no change to the loop.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional, Protocol, Sequence

# Growth is applied after the month's cash flow, so a projection starting
# today does not earn a return on money it has not got yet.
MONTHS_PER_YEAR = 12
# A loan balance below this is paid off; floating point will not reach zero
PAID_OFF = 0.01
# Guards the fixed point between required capital and the wealth tax on it
FIXED_POINT_ROUNDS = 60
FIXED_POINT_TOLERANCE = 1.0


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Bucket:
    """One pot of capital, in today's kroner."""
    name: str
    amount: float
    # None means spendable from day one
    unlock_age: Optional[int] = None
    # Share of market value that counts towards net wealth: equity funds 80,
    # bank deposits 100, a primary residence 25
    valuation_percent: float = 100.0
    # Legally yours, in practice a child's. Never spent, still taxed.
    excluded: bool = False
    # Pension capital is not released as a lump. IPS and a pensjonskapitalbevis
    # pay out over a fixed number of years from the unlock age; the rest keeps
    # growing meanwhile. None means the whole balance is spendable at once.
    payout_years: Optional[int] = None


@dataclass(frozen=True)
class IncomeStream:
    """A pension that arrives as income, not as a balance to draw down.

    Folketrygd and a public tjenestepensjon start on a birthday and run for
    life. They cannot be spent early and they are not taxed as wealth, so
    they belong in the cash flow rather than among the buckets.
    """
    name: str
    monthly: float
    start_age: int
    end_age: Optional[int] = None
    inflation_adjusted: bool = True


@dataclass(frozen=True)
class Obligation:
    """A cost with an end in sight.

    Either a flat `monthly` with an `end_month`, or a loan given as `balance`
    plus `annual_rate`, where the end is amortised out of the payment.
    """
    name: str
    kind: str
    monthly: float
    end_month: Optional[int] = None
    balance: float = 0.0
    annual_rate: float = 0.0
    # Child support follows the index; a fixed-term loan payment does not
    inflation_adjusted: bool = False
    # Whether the money goes into savings once the cost stops
    frees_up_cash: bool = True
    counts_as_debt: bool = True

    @property
    def is_loan(self) -> bool:
        return self.balance > PAID_OFF


@dataclass(frozen=True)
class WealthTax:
    threshold: float
    rate: float
    step2_threshold: Optional[float] = None
    step2_rate: Optional[float] = None
    # Brackets have followed wage growth; if they stop, the tax creeps down
    # the scale on its own and the real threshold shrinks each year
    index_threshold: bool = True

    def on(self, net_wealth: float, inflation_factor: float = 1.0) -> float:
        """Annual tax on net wealth, both given in today's kroner."""
        divisor = 1.0 if self.index_threshold else inflation_factor
        threshold = self.threshold / divisor
        if net_wealth <= threshold:
            return 0.0
        step2 = (self.step2_threshold / divisor) if self.step2_threshold else None
        if step2 is None or net_wealth <= step2:
            return (net_wealth - threshold) * self.rate
        rate2 = self.step2_rate if self.step2_rate is not None else self.rate
        return (step2 - threshold) * self.rate + (net_wealth - step2) * rate2


@dataclass(frozen=True)
class FireInputs:
    start: date
    birth_date: date
    horizon_age: int
    # Both in today's kroner per month. Spending excludes the obligations.
    monthly_spending: float
    monthly_net_income: float
    buckets: Sequence[Bucket]
    obligations: Sequence[Obligation]
    income_streams: Sequence[IncomeStream]
    swr: float
    inflation: float
    nominal_return: float
    wealth_tax: WealthTax
    warnings: Sequence[str] = ()

    @property
    def horizon_months(self) -> int:
        months = (self.horizon_age - age_on(self.birth_date, self.start)) * MONTHS_PER_YEAR
        return max(1, int(round(months)))


# ---------------------------------------------------------------------------
# Return models — the Monte Carlo seam
# ---------------------------------------------------------------------------

class ReturnModel(Protocol):
    """Supplies one month's growth and inflation at a time.

    The projection asks per month and never looks ahead, so a model that
    samples at random, or replays a historical sequence, drops straight in.
    """

    def monthly_real_return(self, month: int) -> float: ...

    def monthly_inflation(self, month: int) -> float: ...


class ConstantReturns:
    """The same assumption every month, which is what a plan is made of."""

    def __init__(self, nominal_annual: float, inflation_annual: float):
        self.nominal_annual = nominal_annual
        self.inflation_annual = inflation_annual
        real_annual = (1.0 + nominal_annual) / (1.0 + inflation_annual) - 1.0
        self.real_annual = real_annual
        self._real = (1.0 + real_annual) ** (1.0 / MONTHS_PER_YEAR) - 1.0
        self._inflation = (1.0 + inflation_annual) ** (1.0 / MONTHS_PER_YEAR) - 1.0

    def monthly_real_return(self, month: int) -> float:
        return self._real

    def monthly_inflation(self, month: int) -> float:
        return self._inflation


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

@dataclass
class YearRow:
    year: int
    age: int
    available: float
    locked: float
    excluded: float
    total: float
    debt: float
    net_wealth: float
    spending: float
    obligations: float
    wealth_tax: float
    saved: float
    withdrawn: float
    working: bool
    # Pensions received this year: income streams plus instalments from a
    # pension pot being paid out. What the capital does NOT have to cover.
    pension_income: float = 0.0
    # Months this row actually covers. The first and last are part-years, and
    # a chart that plots their totals as if they were whole ones lies.
    months: int = MONTHS_PER_YEAR


@dataclass
class ObligationOutcome:
    name: str
    kind: str
    monthly: float
    ends: Optional[date]
    # True when the date was amortised rather than given
    derived: bool
    total_interest: float
    frees_up_cash: bool


@dataclass
class Projection:
    retirement_date: date
    success: bool
    depleted_date: Optional[date]
    # Lowest the spendable pot gets before pension unlocks — the bridge
    bridge_low: Optional[float]
    bridge_low_date: Optional[date]
    first_wealth_tax_year: Optional[int]
    rows: list = field(default_factory=list)
    obligations: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dates and ages
# ---------------------------------------------------------------------------

def add_months(start: date, months: int) -> date:
    total = start.month - 1 + months
    year = start.year + total // MONTHS_PER_YEAR
    month = total % MONTHS_PER_YEAR + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * MONTHS_PER_YEAR + (end.month - start.month)


def age_on(birth_date: date, when: date) -> int:
    years = when.year - birth_date.year
    if (when.month, when.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------

class _Pot:
    """One pot of capital as the month-by-month loop carries it.

    A frozen `Bucket` says what the account is; this says what has happened
    to it so far. They are kept apart so the same inputs can be run through
    the loop many times over, which is what Monte Carlo will need.
    """

    __slots__ = (
        "name", "amount", "valuation", "unlock_age", "payout_years",
        "excluded", "payout_months_left", "unlocked",
    )

    def __init__(self, bucket: Bucket):
        self.name = bucket.name
        self.amount = bucket.amount
        self.valuation = bucket.valuation_percent / 100.0
        self.unlock_age = bucket.unlock_age
        self.payout_years = bucket.payout_years
        self.excluded = bucket.excluded
        self.payout_months_left: Optional[int] = None
        self.unlocked = bucket.unlock_age is None

    @property
    def spendable(self) -> bool:
        """Free to draw on this month.

        A pot being paid out in instalments is not: the instalment arrives as
        income on its own schedule and the rest cannot be touched.
        """
        return self.unlocked and not self.excluded and self.payout_years is None

    @property
    def taxable(self) -> float:
        return self.amount * self.valuation


def _draw_order(pots: Sequence["_Pot"]) -> list["_Pot"]:
    """Spendable pots, most heavily taxed first.

    Which pot a krone comes out of is free money or a free loss. Bank deposits
    count at full value towards net wealth, share savings accounts at eighty
    per cent, pension capital at nothing. Spending the taxed money first
    leaves the untaxed money compounding for longer and shrinks every future
    wealth tax assessment along the way.

    It costs nothing to get right and nothing in the ledger has to change for
    it, which is why the order is derived rather than configured.
    """
    return sorted(
        (p for p in pots if p.spendable),
        key=lambda p: p.valuation, reverse=True,
    )


def _apply_cash(pots: Sequence["_Pot"], delta: float) -> None:
    """Put money into the pots, or take it out, one month's worth.

    Money going in covers an overdraft first and then follows the mix already
    held, because that is where a standing order actually sends it. Money
    coming out follows the draw order. If every pot is empty the shortfall is
    left on the most heavily taxed one, which is what makes the plan visibly
    fail rather than quietly balance.
    """
    order = _draw_order(pots)
    if not order:
        return

    if delta >= 0:
        for pot in order:
            if delta <= 0:
                break
            if pot.amount < 0:
                covered = min(delta, -pot.amount)
                pot.amount += covered
                delta -= covered
        if delta <= 0:
            return
        positive = [p for p in order if p.amount > 0]
        total = sum(p.amount for p in positive)
        if total <= 0:
            order[0].amount += delta
            return
        for pot in positive:
            pot.amount += delta * pot.amount / total
        return

    short = -delta
    for pot in order:
        if short <= 0:
            break
        if pot.amount <= 0:
            continue
        taken = min(short, pot.amount)
        pot.amount -= taken
        short -= taken
    if short > 0:
        order[0].amount -= short


def project(
    inputs: FireInputs,
    returns: ReturnModel,
    retirement_month: int,
    growth_only: bool = False,
) -> Projection:
    """Run the plan month by month from `inputs.start` to the horizon.

    `retirement_month` is the month index at which earned income stops. Pass
    the horizon to ask what happens if the work never does.

    `growth_only` drops every cash flow and lets the pots compound on their
    own. It answers a different question — what today's capital becomes if
    nothing is ever added to it — and is drawn alongside the real projection
    so the two can be compared.
    """
    horizon = inputs.horizon_months
    retirement_month = max(0, min(retirement_month, horizon))

    # Each pot carries its own taxable value. One blended rate would not
    # survive a pension account worth nothing for wealth tax sitting beside a
    # fund portfolio valued at eighty per cent.
    pots = [_Pot(b) for b in inputs.buckets]

    loan_balance = [ob.balance for ob in inputs.obligations]
    interest_paid = [0.0 for _ in inputs.obligations]
    payoff_month: list[Optional[int]] = [None for _ in inputs.obligations]

    inflation_factor = 1.0
    wealth_tax_monthly = 0.0
    first_wealth_tax_year: Optional[int] = None
    depleted_month: Optional[int] = None
    bridge_low: Optional[float] = None
    bridge_low_month: Optional[int] = None

    rows: list[YearRow] = []
    year_months = 0
    year_spending = year_obligations = year_tax = 0.0
    year_saved = year_withdrawn = year_pension = 0.0

    # The first assessment is on today's wealth, debt included, so year one is
    # neither tax-free nor taxed on a gross figure
    if not growth_only:
        opening_debt = sum(ob.balance for ob in inputs.obligations if ob.counts_as_debt)
        wealth_tax_monthly = inputs.wealth_tax.on(
            _net_wealth(sum(p.taxable for p in pots), opening_debt), 1.0,
        ) / MONTHS_PER_YEAR

    for month in range(horizon):
        when = add_months(inputs.start, month)
        age = age_on(inputs.birth_date, when)
        working = month < retirement_month and not growth_only

        for pot in pots:
            if not pot.unlocked and pot.unlock_age is not None and age >= pot.unlock_age:
                pot.unlocked = True
                if pot.payout_years:
                    pot.payout_months_left = pot.payout_years * MONTHS_PER_YEAR

        pension = 0.0
        debt = 0.0
        obligation_cost = 0.0
        spending = 0.0
        saved = withdrawn = 0.0

        if not growth_only:
            # Pension capital being paid out: the instalment is recomputed
            # every month so returns earned during the payout are shared out
            # too, instead of being stranded in the final month.
            for pot in pots:
                if pot.payout_months_left:
                    instalment = pot.amount / pot.payout_months_left
                    pot.amount -= instalment
                    pot.payout_months_left -= 1
                    pension += instalment

            for stream in inputs.income_streams:
                if age < stream.start_age:
                    continue
                if stream.end_age is not None and age >= stream.end_age:
                    continue
                pension += (
                    stream.monthly if stream.inflation_adjusted
                    else stream.monthly / inflation_factor
                )

            for i, ob in enumerate(inputs.obligations):
                cost_nominal = 0.0
                running = ob.end_month is None or month < ob.end_month
                if ob.is_loan:
                    if loan_balance[i] > PAID_OFF and running:
                        interest = loan_balance[i] * ob.annual_rate / MONTHS_PER_YEAR
                        payment = min(ob.monthly, loan_balance[i] + interest)
                        loan_balance[i] += interest - payment
                        interest_paid[i] += interest
                        cost_nominal = payment
                        if loan_balance[i] <= PAID_OFF:
                            loan_balance[i] = 0.0
                            payoff_month[i] = month
                    elif loan_balance[i] > PAID_OFF and not running:
                        # End date reached with principal left: the rest is due
                        payoff_month[i] = payoff_month[i] or month
                        loan_balance[i] = 0.0
                elif running:
                    cost_nominal = ob.monthly
                elif payoff_month[i] is None and ob.end_month is not None:
                    payoff_month[i] = ob.end_month

                if cost_nominal:
                    obligation_cost += (
                        cost_nominal if ob.inflation_adjusted
                        else cost_nominal / inflation_factor
                    )
                if ob.counts_as_debt:
                    debt += loan_balance[i] / inflation_factor

            spending = inputs.monthly_spending
            outgoing = spending + obligation_cost + wealth_tax_monthly
            earned = inputs.monthly_net_income if working else 0.0
            delta = earned + pension - outgoing
            saved = max(0.0, delta)
            withdrawn = max(0.0, -delta)
            _apply_cash(pots, delta)

            if sum(p.amount for p in pots if p.spendable) < 0 and depleted_month is None:
                depleted_month = month

        growth = 1.0 + returns.monthly_real_return(month)
        for pot in pots:
            if pot.amount > 0:
                pot.amount *= growth
        inflation_factor *= 1.0 + returns.monthly_inflation(month)

        available = sum(p.amount for p in pots if p.spendable)
        locked_total = sum(
            p.amount for p in pots if not p.excluded and not p.spendable
        )
        excluded_total = sum(p.amount for p in pots if p.excluded)

        # The bridge is only a question once the income stops: how low the
        # spendable pot gets while the rest is still locked away
        if locked_total and not working and not growth_only:
            if bridge_low is None or available < bridge_low:
                bridge_low, bridge_low_month = available, month

        year_months += 1
        year_spending += spending
        year_obligations += obligation_cost
        year_tax += wealth_tax_monthly
        year_saved += saved
        year_withdrawn += withdrawn
        year_pension += pension

        if when.month == 12 or month == horizon - 1:
            net_wealth = _net_wealth(sum(p.taxable for p in pots), debt)
            rows.append(YearRow(
                year=when.year,
                age=age,
                available=available,
                locked=locked_total,
                excluded=excluded_total,
                total=available + locked_total + excluded_total,
                debt=debt,
                net_wealth=net_wealth,
                spending=year_spending,
                obligations=year_obligations,
                wealth_tax=year_tax,
                saved=year_saved,
                withdrawn=year_withdrawn,
                working=working,
                pension_income=year_pension,
                months=year_months,
            ))
            if year_tax > 0 and first_wealth_tax_year is None:
                first_wealth_tax_year = when.year
            year_months = 0
            year_spending = year_obligations = year_tax = 0.0
            year_saved = year_withdrawn = year_pension = 0.0

            if when.month == 12 and not growth_only:
                # Assessed on 31 December, paid over the year that follows
                annual = inputs.wealth_tax.on(net_wealth, inflation_factor)
                wealth_tax_monthly = annual / MONTHS_PER_YEAR

    return Projection(
        retirement_date=add_months(inputs.start, retirement_month),
        success=depleted_month is None,
        depleted_date=add_months(inputs.start, depleted_month) if depleted_month is not None else None,
        bridge_low=bridge_low,
        bridge_low_date=add_months(inputs.start, bridge_low_month) if bridge_low_month is not None else None,
        first_wealth_tax_year=first_wealth_tax_year,
        rows=rows,
        obligations=[
            ObligationOutcome(
                name=ob.name,
                kind=ob.kind,
                monthly=ob.monthly,
                ends=(
                    add_months(inputs.start, payoff_month[i] + 1)
                    if payoff_month[i] is not None else None
                ),
                derived=ob.is_loan and ob.end_month is None,
                total_interest=interest_paid[i],
                frees_up_cash=ob.frees_up_cash,
            )
            for i, ob in enumerate(inputs.obligations)
        ],
        warnings=list(inputs.warnings),
    )


def _spendable_valuation(buckets: Iterable[Bucket]) -> float:
    """Taxable share of the pots that money is actually saved into.

    Pension capital is left out: it cannot be paid into freely, and valuing
    future savings as if they were pension would hide the wealth tax.
    """
    total = weighted = 0.0
    for b in buckets:
        if b.excluded or b.unlock_age is not None or b.amount <= 0:
            continue
        total += b.amount
        weighted += b.amount * b.valuation_percent / 100.0
    if total <= 0:
        return 1.0
    return weighted / total


def _net_wealth(taxable_capital: float, debt: float) -> float:
    return max(0.0, taxable_capital - debt)


# ---------------------------------------------------------------------------
# The two headline answers
# ---------------------------------------------------------------------------

@dataclass
class FireNumber:
    perpetual_annual_spending: float
    base_capital: float
    wealth_tax_annual: float
    wealth_tax_capital: float
    bridge_capital: float
    # Present value of the pensions, which the capital does not have to raise
    pension_capital: float
    total: float


def fire_number(inputs: FireInputs) -> FireNumber:
    """Capital needed to stop for good, in today's kroner.

    Costs that never end are capitalised at the withdrawal rate. Costs that do
    end are not — carrying them to the grave would overstate the target by a
    long way — so they are added at their present value instead.

    The wealth tax is charged on the capital it is paid from, which makes the
    answer its own input. A few rounds of substitution settle it.

    Pensions still to come are subtracted at their present value, the mirror
    of how costs that end are added. Both are bounded by the horizon, so a
    pension paid for life counts only as far as the plan runs.
    """
    perpetual_monthly = inputs.monthly_spending + sum(
        ob.monthly for ob in inputs.obligations
        if ob.end_month is None and not ob.is_loan
    )
    perpetual_annual = perpetual_monthly * MONTHS_PER_YEAR
    base = perpetual_annual / inputs.swr if inputs.swr > 0 else 0.0

    valuation = _spendable_valuation(inputs.buckets)
    capital = base
    tax = 0.0
    for _ in range(FIXED_POINT_ROUNDS):
        tax = inputs.wealth_tax.on(capital * valuation)
        nxt = (perpetual_annual + tax) / inputs.swr if inputs.swr > 0 else 0.0
        if abs(nxt - capital) < FIXED_POINT_TOLERANCE:
            capital = nxt
            break
        capital = nxt

    real_monthly = (1.0 + _real_rate(inputs)) ** (1.0 / MONTHS_PER_YEAR) - 1.0
    bridge = sum(
        _present_value(ob, inputs, real_monthly)
        for ob in inputs.obligations
        if ob.end_month is not None or ob.is_loan
    )
    pension = sum(
        _stream_present_value(st, inputs, real_monthly)
        for st in inputs.income_streams
    )

    return FireNumber(
        perpetual_annual_spending=perpetual_annual,
        base_capital=base,
        wealth_tax_annual=tax,
        wealth_tax_capital=capital - base,
        bridge_capital=bridge,
        pension_capital=pension,
        total=max(0.0, capital + bridge - pension),
    )


def _real_rate(inputs: FireInputs) -> float:
    return (1.0 + inputs.nominal_return) / (1.0 + inputs.inflation) - 1.0


def _present_value(ob: Obligation, inputs: FireInputs, real_monthly: float) -> float:
    """What it costs today to cover a finite obligation until it ends."""
    horizon = inputs.horizon_months
    balance = ob.balance
    inflation_monthly = (1.0 + inputs.inflation) ** (1.0 / MONTHS_PER_YEAR) - 1.0
    inflation_factor = 1.0
    discount = 1.0
    total = 0.0
    for month in range(horizon):
        running = ob.end_month is None or month < ob.end_month
        if not running:
            break
        if ob.is_loan:
            if balance <= PAID_OFF:
                break
            interest = balance * ob.annual_rate / MONTHS_PER_YEAR
            payment = min(ob.monthly, balance + interest)
            balance += interest - payment
        else:
            payment = ob.monthly
        real = payment if ob.inflation_adjusted else payment / inflation_factor
        total += real / discount
        inflation_factor *= 1.0 + inflation_monthly
        discount *= 1.0 + real_monthly
    return total


def _stream_present_value(
    stream: IncomeStream, inputs: FireInputs, real_monthly: float
) -> float:
    """What a pension still to come is worth today, in today's kroner.

    The mirror of `_present_value`: an obligation is money leaving, a stream
    is money arriving, and both are bounded by the horizon. A pension paid
    for life is counted only as far as the plan runs, which is the same
    convention every other figure here follows.
    """
    horizon = inputs.horizon_months
    inflation_monthly = (1.0 + inputs.inflation) ** (1.0 / MONTHS_PER_YEAR) - 1.0
    inflation_factor = 1.0
    discount = 1.0
    total = 0.0
    for month in range(horizon):
        age = age_on(inputs.birth_date, add_months(inputs.start, month))
        running = age >= stream.start_age and (
            stream.end_age is None or age < stream.end_age
        )
        if running:
            real = (
                stream.monthly if stream.inflation_adjusted
                else stream.monthly / inflation_factor
            )
            total += real / discount
        inflation_factor *= 1.0 + inflation_monthly
        discount *= 1.0 + real_monthly
    return total


def earliest_retirement(
    inputs: FireInputs,
    returns: ReturnModel,
    latest_age: int = 75,
) -> Optional[Projection]:
    """The first month the plan survives to the horizon.

    Retiring later is always at least as good — another month of income
    instead of a month of withdrawals — so the answer can be bisected. The
    result is confirmed by checking that the month before it fails, which
    catches any case where that assumption does not hold.
    """
    latest = min(
        inputs.horizon_months,
        max(0, (latest_age - age_on(inputs.birth_date, inputs.start)) * MONTHS_PER_YEAR),
    )
    if latest <= 0:
        return None
    if not project(inputs, returns, latest).success:
        return None

    low, high = 0, latest
    while low < high:
        mid = (low + high) // 2
        if project(inputs, returns, mid).success:
            high = mid
        else:
            low = mid + 1

    while low > 0 and project(inputs, returns, low - 1).success:
        low -= 1
    return project(inputs, returns, low)


# ---------------------------------------------------------------------------
# Reading the ledger
#
# The projection above knows nothing about accounts. This section turns a
# ledger into its inputs: what the pots are worth, what a month costs, what a
# month earns. Keeping it separate is what lets the simulation be run tens of
# thousands of times without touching the database.
# ---------------------------------------------------------------------------

AVERAGE_DAYS_PER_MONTH = 30.44


class FireDisabled(Exception):
    pass


def build_inputs(db, settings, as_of: Optional[date] = None) -> FireInputs:
    """Assemble the projection's inputs from the ledger behind `settings`."""
    from sqlalchemy import func as sa_func

    from .models import (
        Account,
        AccountType,
        FireRole,
        JournalEntry,
        Transaction,
        TransactionStatus,
    )

    booked = (TransactionStatus.POSTED, TransactionStatus.RECONCILED)
    as_of = as_of or date.today()
    start = date(as_of.year, as_of.month, 1)

    if not settings.is_enabled:
        raise FireDisabled("FIRE-beregning er ikke aktivert for dette regnskapet")
    if not settings.birth_date:
        raise FireDisabled(
            "Fødselsdato mangler. Bundet kapital frigjøres etter alder, ikke dato."
        )

    warnings: list[str] = []
    excluded_ids = {e.account_id for e in settings.excluded_accounts}
    # A value-change counter-account is growth already assumed by the return
    # rate; counting it as income too would pay for retirement twice
    value_change_ids = {
        row[0] for row in db.query(Account.value_change_account_id)
        .filter(Account.value_change_account_id.isnot(None)).distinct()
    }
    # Where an obligation's cost is already booked. Counting both the
    # obligation and the booking would charge the same krone twice: a
    # mortgage pays interest onto 7101 every month and child support onto an
    # expense account of its own. The balance account, if there is one, is a
    # different link and must not be confused with this.
    obligation_account_ids = {
        ob.cost_account_id for ob in settings.obligations
        if ob.is_active and ob.cost_account_id
    }

    def balance(account_id: int) -> float:
        total = db.query(
            sa_func.coalesce(sa_func.sum(JournalEntry.debit - JournalEntry.credit), 0)
        ).join(
            Transaction, Transaction.id == JournalEntry.transaction_id
        ).filter(
            JournalEntry.account_id == account_id,
            Transaction.status.in_(booked),
            Transaction.transaction_date <= as_of,
        ).scalar()
        return float(total or 0)

    # --- capital -----------------------------------------------------------
    buckets: list[Bucket] = []
    assets = db.query(Account).filter(
        Account.ledger_id == settings.ledger_id,
        Account.account_type == AccountType.ASSET,
        Account.is_active.is_(True),
    ).order_by(Account.account_number).all()

    for account in assets:
        amount = balance(account.id)
        role = account.fire_role
        if role is None:
            if abs(amount) > 1:
                warnings.append(
                    f"{account.account_number} {account.account_name} "
                    f"({amount:,.0f}) er ikke klassifisert og teller ikke med."
                )
            continue
        if role == FireRole.IGNORED or amount == 0:
            continue
        if amount < 0:
            # An overdrawn account is a real claim on the capital, but only
            # a spendable one can carry a negative balance sensibly
            if role != FireRole.AVAILABLE:
                warnings.append(
                    f"{account.account_number} {account.account_name} står i "
                    f"minus ({amount:,.0f}) og er utelatt."
                )
                continue
            warnings.append(
                f"{account.account_number} {account.account_name} står i minus "
                f"({amount:,.0f}) og trekker ned tilgjengelig kapital."
            )
        valuation = (
            float(account.wealth_valuation_percent)
            if account.wealth_valuation_percent is not None else 100.0
        )
        buckets.append(Bucket(
            name=f"{account.account_number} {account.account_name}",
            amount=amount,
            unlock_age=account.fire_unlock_age if role == FireRole.LOCKED else None,
            valuation_percent=valuation,
            excluded=role == FireRole.EXCLUDED,
            payout_years=(
                account.fire_payout_years if role == FireRole.LOCKED else None
            ),
        ))
        if role == FireRole.LOCKED and account.fire_unlock_age is None:
            warnings.append(
                f"{account.account_number} {account.account_name} er merket bundet "
                f"uten frigivelsesalder, og regnes som tilgjengelig."
            )

    # --- what a month costs and earns --------------------------------------
    months, window_start = _window(db, settings.ledger_id, settings.lookback_months, as_of)

    def flow(ledger_id: int, account_type, skip: set, since: date) -> float:
        rows = db.query(
            JournalEntry.account_id,
            sa_func.coalesce(sa_func.sum(JournalEntry.debit - JournalEntry.credit), 0),
        ).join(
            Transaction, Transaction.id == JournalEntry.transaction_id
        ).join(
            Account, Account.id == JournalEntry.account_id
        ).filter(
            Account.ledger_id == ledger_id,
            Account.account_type == account_type,
            Transaction.status.in_(booked),
            Transaction.transaction_date >= since,
            Transaction.transaction_date <= as_of,
        ).group_by(JournalEntry.account_id).all()
        sign = 1.0 if account_type == AccountType.EXPENSE else -1.0
        return sum(float(amount) * sign for account_id, amount in rows
                   if account_id not in skip)

    own_spending = flow(
        settings.ledger_id, AccountType.EXPENSE,
        excluded_ids | obligation_account_ids, window_start,
    )
    income = flow(
        settings.ledger_id, AccountType.REVENUE,
        excluded_ids | value_change_ids, window_start,
    )

    shared_spending = 0.0
    if settings.shared_ledger_id and settings.shared_share_percent:
        share = float(settings.shared_share_percent) / 100.0
        shared_months, shared_start = _window(
            db, settings.shared_ledger_id, settings.lookback_months, as_of
        )
        # Each ledger is summed over its own window and divided by its own
        # span: a shared ledger opened earlier has more months of history
        shared_total = flow(
            settings.shared_ledger_id, AccountType.EXPENSE,
            excluded_ids | obligation_account_ids, shared_start,
        )
        shared_spending = shared_total * share / shared_months

    monthly_spending = own_spending / months + shared_spending
    monthly_income = income / months

    if monthly_spending <= 0:
        warnings.append(
            "Fant ingen kostnader i perioden. Forbruket må være større enn null "
            "for at beregningen skal si noe."
        )

    # --- obligations -------------------------------------------------------
    obligations: list[Obligation] = []
    for ob in settings.obligations:
        if not ob.is_active:
            continue
        loan_balance = float(ob.balance) if ob.balance is not None else 0.0
        if not loan_balance and ob.account_id and ob.kind.value == "LOAN":
            loan_balance = abs(balance(ob.account_id))
        end_month = None
        if ob.end_date:
            end_month = max(0, months_between(start, ob.end_date))
        obligations.append(Obligation(
            name=ob.name,
            kind=ob.kind.value,
            monthly=float(ob.monthly_amount or 0),
            end_month=end_month,
            balance=loan_balance,
            annual_rate=float(ob.interest_percent or 0) / 100.0,
            inflation_adjusted=bool(ob.inflation_adjusted),
            frees_up_cash=bool(ob.frees_up_cash),
            counts_as_debt=bool(ob.counts_as_debt),
        ))
        if ob.kind.value == "LOAN" and loan_balance and not ob.interest_percent:
            warnings.append(
                f"{ob.name} har saldo, men ingen rente. Nedbetalingsdatoen blir "
                f"for tidlig."
            )

    # --- pensions that arrive as income ------------------------------------
    income_streams: list[IncomeStream] = []
    for st in settings.income_streams:
        if not st.is_active:
            continue
        income_streams.append(IncomeStream(
            name=st.name,
            monthly=float(st.monthly_amount or 0),
            start_age=st.start_age,
            end_age=st.end_age,
            inflation_adjusted=bool(st.inflation_adjusted),
        ))
        if st.start_age > settings.horizon_age:
            warnings.append(
                f"{st.name} starter ved {st.start_age} år, etter at beregningen "
                f"slutter ved {settings.horizon_age}. Den teller ikke med."
            )

    for bucket in buckets:
        if bucket.unlock_age is not None and bucket.unlock_age >= settings.horizon_age:
            warnings.append(
                f"{bucket.name} frigjøres ved {bucket.unlock_age} år, samtidig med "
                f"eller etter at beregningen slutter ved {settings.horizon_age}. "
                f"Den blir stående urørt."
            )

    return FireInputs(
        start=start,
        birth_date=settings.birth_date,
        horizon_age=settings.horizon_age,
        monthly_spending=monthly_spending,
        monthly_net_income=monthly_income,
        buckets=buckets,
        obligations=obligations,
        income_streams=income_streams,
        swr=float(settings.swr_percent) / 100.0,
        inflation=float(settings.inflation_percent) / 100.0,
        nominal_return=float(settings.expected_return_percent) / 100.0,
        wealth_tax=WealthTax(
            threshold=float(settings.wealth_tax_threshold),
            rate=float(settings.wealth_tax_rate_percent) / 100.0,
            step2_threshold=(
                float(settings.wealth_tax_step2_threshold)
                if settings.wealth_tax_step2_threshold is not None else None
            ),
            step2_rate=(
                float(settings.wealth_tax_step2_rate_percent) / 100.0
                if settings.wealth_tax_step2_rate_percent is not None else None
            ),
            index_threshold=bool(settings.wealth_tax_index_threshold),
        ),
        warnings=warnings,
    )


def _window(db, ledger_id: int, lookback_months: int, as_of: date) -> tuple[float, date]:
    """How far back to read, and how many months that actually covers.

    A ledger opened in January cannot show twelve months of spending in
    October. Dividing by twelve anyway would halve the apparent cost of
    living, so the divisor is the span that really has data in it.

    Only entries on income and expense accounts count towards that span. An
    opening balance carries the date the house was bought, which says nothing
    about how long the ledger has been recording what a month costs.
    """
    from sqlalchemy import func as sa_func

    from .models import Account, AccountType, JournalEntry, Transaction

    requested = add_months(date(as_of.year, as_of.month, 1), -max(1, lookback_months))
    earliest = db.query(sa_func.min(Transaction.transaction_date)).join(
        JournalEntry, JournalEntry.transaction_id == Transaction.id
    ).join(
        Account, Account.id == JournalEntry.account_id
    ).filter(
        Transaction.ledger_id == ledger_id,
        Account.account_type.in_((AccountType.REVENUE, AccountType.EXPENSE)),
    ).scalar()
    window_start = max(requested, earliest) if earliest else requested
    days = max(1, (as_of - window_start).days)
    return max(1.0, days / AVERAGE_DAYS_PER_MONTH), window_start
