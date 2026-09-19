"""Monthly settlement calculation.

Forecasts a ledger's shared expenses for a month and splits them between the
configured members. Everything is driven by SettlementSettings; nothing here is
specific to a particular household.

Forecast for the month = booked expenses so far
                       + open planned transactions (registered invoices)
                       + recurring bills recognised from history, not yet seen
                         this month and not covered by a planned transaction
                       + pro-rated estimate of variable spending

Expenses are counted when booked (accrual view), so credit card purchases count
in the month they happen and the card settlement itself is never counted.
"""
import calendar
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import (
    Account,
    AccountType,
    BankAccount,
    BankAccountType,
    JournalEntry,
    PlannedTransaction,
    PlannedTransactionStatus,
    SettlementSettings,
    Transaction,
    TransactionStatus,
)

BOOKED_STATUSES = (TransactionStatus.POSTED, TransactionStatus.RECONCILED)

# Months of history scanned when looking for recurring bills
RECURRING_HISTORY_MONTHS = 12
# A counterparty is "recurring" when its monthly total is stable and it shows
# up only a few times per month (bills, not grocery runs)
RECURRING_MAX_TX_PER_MONTH = 2.0
RECURRING_MAX_CV = 0.25
# Occurrences used for the amount estimate and stability check
RECURRING_RECENT_WINDOW = 4
# A counterparty seen in this many of the last 12 months, about once a month,
# is a bill even if the amount varies (power, phone with usage)
RECURRING_MIN_MONTHS_FOR_VARIABLE_BILL = 6
RECURRING_MAX_TX_FOR_VARIABLE_BILL = 1.5
# A planned transaction is taken to cover a recurring candidate when the
# amounts are within this fraction (insurance premiums etc. drift year to year)
PLANNED_AMOUNT_TOLERANCE = Decimal("0.15")

ZERO = Decimal("0.00")
_REFERENCE_RE = re.compile(r"\d[\d/.\-]*")
_NON_ALPHA_RE = re.compile(r"[^a-zæøåäöüéè ]")
_STOP_TOKENS = {
    "efaktura", "avtalegiro", "betaling", "nettbank", "vipps", "mobilepay",
    "til", "fra", "crv", "og", "as", "asa", "sa", "ab", "the", "lt",
}


def normalize_key(description: str) -> str:
    """Collapse a bank description to a counterparty key.

    Reference numbers, KID and card prefixes are stripped so "12345 - eFaktura:
    678/Fremtind Forsikring" and "99999 - eFaktura: 111/Fremtind Forsikring"
    share a key. Descriptions with no words at all (e.g. "Til:25518205229")
    fall back to the cleaned digits, since a bare account number is stable.
    """
    s = (description or "").lower().replace("crv*", " ")
    words = _NON_ALPHA_RE.sub(" ", _REFERENCE_RE.sub(" ", s))
    tokens = [t for t in words.split() if len(t) > 1 and t not in _STOP_TOKENS]
    if tokens:
        return " ".join(tokens[:3])
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]", " ", s)).strip()


def _q(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _month_index(d: date) -> int:
    return d.year * 12 + (d.month - 1)


def _month_from_index(idx: int) -> tuple[int, int]:
    return idx // 12, idx % 12 + 1


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


@dataclass
class _KeyStats:
    # month index -> total expense amount that month
    monthly_totals: dict = field(default_factory=lambda: defaultdict(lambda: ZERO))
    # month index -> number of transactions that month
    monthly_counts: dict = field(default_factory=lambda: defaultdict(int))
    # month index -> earliest day of month seen
    monthly_first_day: dict = field(default_factory=dict)
    sample_description: str = ""


class SettlementDisabled(Exception):
    pass


def calculate_settlement(
    db: Session,
    settings: SettlementSettings,
    year: int,
    month: int,
    as_of: Optional[date] = None,
) -> dict:
    if not settings.is_enabled:
        raise SettlementDisabled()

    ledger_id = settings.ledger_id
    as_of = as_of or date.today()
    month_start, month_end = _month_bounds(year, month)
    target_idx = _month_index(month_start)
    excluded_ids = {e.account_id for e in settings.excluded_accounts}

    # Effective "today" clamped to the month: before it -> nothing booked yet,
    # after it -> month is complete and there is nothing left to forecast
    effective_as_of = min(max(as_of, month_start - timedelta(days=1)), month_end)
    days_in_month = (month_end - month_start).days + 1
    days_remaining = (month_end - effective_as_of).days
    month_complete = days_remaining == 0

    # ------------------------------------------------------------------
    # Expense history: one row per (transaction, expense entry)
    # ------------------------------------------------------------------
    history_start = _month_bounds(*_month_from_index(target_idx - RECURRING_HISTORY_MONTHS))[0]
    rows = (
        db.query(
            Transaction.id,
            Transaction.transaction_date,
            Transaction.description,
            JournalEntry.account_id,
            (JournalEntry.debit - JournalEntry.credit).label("amount"),
        )
        .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
        .join(Account, Account.id == JournalEntry.account_id)
        .filter(
            Transaction.ledger_id == ledger_id,
            Transaction.status.in_(BOOKED_STATUSES),
            Transaction.transaction_date >= history_start,
            Transaction.transaction_date <= month_end,
            Account.account_type == AccountType.EXPENSE,
        )
        .all()
    )

    matched_tx_ids = {
        tx_id for (tx_id,) in db.query(PlannedTransaction.matched_transaction_id).filter(
            PlannedTransaction.ledger_id == ledger_id,
            PlannedTransaction.status == PlannedTransactionStatus.MATCHED,
            PlannedTransaction.matched_transaction_id.isnot(None),
        )
    }

    stats: dict[str, _KeyStats] = defaultdict(_KeyStats)
    month_totals: dict[int, Decimal] = defaultdict(lambda: ZERO)
    # amounts this month per key, and per transaction (for planned dedup)
    tx_amount_by_key_month: dict[tuple[str, int], Decimal] = defaultdict(lambda: ZERO)
    invoice_amount_by_key_month: dict[tuple[str, int], Decimal] = defaultdict(lambda: ZERO)
    excluded_booked = ZERO
    seen_tx_month: set[tuple[str, int]] = set()

    for tx_id, tx_date, description, account_id, amount in rows:
        amount = Decimal(amount or 0)
        idx = _month_index(tx_date)
        if account_id in excluded_ids:
            if idx == target_idx:
                excluded_booked += amount
            continue

        key = normalize_key(description)
        month_totals[idx] += amount
        tx_amount_by_key_month[(key, idx)] += amount

        st = stats[key]
        st.monthly_totals[idx] += amount
        if (str(tx_id), idx) not in seen_tx_month:
            seen_tx_month.add((str(tx_id), idx))
            st.monthly_counts[idx] += 1
        st.monthly_first_day[idx] = min(st.monthly_first_day.get(idx, 31), tx_date.day)
        if not st.sample_description:
            st.sample_description = description

        if tx_id in matched_tx_ids:
            invoice_amount_by_key_month[(key, idx)] += amount

    booked_total = _q(month_totals.get(target_idx, ZERO))

    # ------------------------------------------------------------------
    # Recurring bills from history (target month excluded from detection)
    # ------------------------------------------------------------------
    recurring_keys: dict[str, dict] = {}
    for key, st in stats.items():
        if not key:
            continue
        past_months = sorted(m for m in st.monthly_totals if m < target_idx and st.monthly_totals[m] > 0)
        if len(past_months) < 2:
            continue

        avg_tx = statistics.mean(st.monthly_counts[m] for m in past_months)
        if avg_tx > RECURRING_MAX_TX_PER_MONTH:
            continue

        # Stability is judged on the recent occurrences only, so seasonal
        # drift (power bills) or an old one-off double payment does not
        # disqualify a bill that is clearly regular now
        recent_totals = [float(st.monthly_totals[m]) for m in past_months[-RECURRING_RECENT_WINDOW:]]
        mean_total = statistics.mean(recent_totals)
        if mean_total <= 0:
            continue
        cv = statistics.pstdev(recent_totals) / mean_total if len(recent_totals) > 1 else 0.0
        very_regular = (
            len(past_months) >= RECURRING_MIN_MONTHS_FOR_VARIABLE_BILL
            and avg_tx <= RECURRING_MAX_TX_FOR_VARIABLE_BILL
        )
        if cv > RECURRING_MAX_CV and not very_regular:
            continue

        period = _detect_period(past_months, target_idx)
        if period is None:
            continue

        recurring_keys[key] = {
            "period_months": period,
            "expected_this_month": (target_idx - past_months[-1]) % period == 0,
            "typical_amount": _q(statistics.median(recent_totals)),
            "typical_day": int(statistics.median(st.monthly_first_day[m] for m in past_months)),
            "description": st.sample_description,
            "last_seen": _month_from_index(past_months[-1]),
        }

    # ------------------------------------------------------------------
    # Planned transactions (registered invoices) due this month
    # ------------------------------------------------------------------
    open_plans = (
        db.query(PlannedTransaction)
        .filter(
            PlannedTransaction.ledger_id == ledger_id,
            PlannedTransaction.status == PlannedTransactionStatus.OPEN,
            PlannedTransaction.expected_date >= month_start,
            PlannedTransaction.expected_date <= month_end,
        )
        .order_by(PlannedTransaction.expected_date)
        .all()
    )
    planned_lines = []
    for p in open_plans:
        if p.suggested_account_id in excluded_ids:
            continue
        if month_complete:
            # Nothing more will be paid in a closed month; unmatched plans
            # there are stale, not upcoming
            continue
        planned_lines.append({
            "planned_transaction_id": p.id,
            "receipt_id": p.receipt_id,
            "description": p.description,
            "expected_date": p.expected_date,
            "amount": _q(p.amount),
            "overdue": p.expected_date < effective_as_of,
        })
    planned_total = _q(sum((l["amount"] for l in planned_lines), ZERO))

    # ------------------------------------------------------------------
    # Recurring bills still expected this month
    # ------------------------------------------------------------------
    recurring_lines = []
    planned_keys = [normalize_key(l["description"]) for l in planned_lines]
    for key, info in recurring_keys.items():
        if month_complete or not info["expected_this_month"]:
            continue
        if (key, target_idx) in tx_amount_by_key_month:
            continue  # already booked this month
        if _covered_by_planned(key, info["typical_amount"], planned_lines, planned_keys):
            continue
        recurring_lines.append({
            "key": key,
            "description": info["description"],
            "expected_day": info["typical_day"],
            "amount": info["typical_amount"],
            "period_months": info["period_months"],
        })
    recurring_lines.sort(key=lambda l: l["expected_day"])
    recurring_total = _q(sum((l["amount"] for l in recurring_lines), ZERO))

    # ------------------------------------------------------------------
    # Variable spending: what is left after recurring bills and invoices
    # ------------------------------------------------------------------
    def fixed_part(idx: int) -> Decimal:
        # Recurring counterparties plus matched invoices from other
        # counterparties; a recurring key's invoices are already in the first sum
        fixed = sum(
            (tx_amount_by_key_month.get((k, idx), ZERO) for k in recurring_keys),
            ZERO,
        )
        invoices = sum(
            (amt for (k, m), amt in invoice_amount_by_key_month.items()
             if m == idx and k not in recurring_keys),
            ZERO,
        )
        return fixed + invoices

    lookback = max(1, settings.variable_lookback_months)
    lookback_months = [target_idx - i for i in range(1, lookback + 1)]
    variable_history = [
        float(month_totals.get(m, ZERO) - fixed_part(m))
        for m in lookback_months
        if m in month_totals
    ]
    typical_variable = _q(statistics.median(variable_history)) if variable_history else ZERO
    typical_variable = max(typical_variable, ZERO)

    booked_fixed = _q(fixed_part(target_idx))
    booked_variable = _q(booked_total - booked_fixed)
    variable_remaining = ZERO if month_complete else _q(
        typical_variable * Decimal(days_remaining) / Decimal(days_in_month)
    )

    forecast_total = _q(booked_total + planned_total + recurring_total + variable_remaining)

    # ------------------------------------------------------------------
    # Members: share of forecast, adjusted for own withdrawals and deposits
    # ------------------------------------------------------------------
    members_out = []
    for m in sorted(settings.members, key=lambda m: m.user_id):
        share = _q(forecast_total * Decimal(m.share_percent) / Decimal(100))
        withdrawals = ZERO
        contributed = ZERO
        if m.deposit_account_id:
            row = (
                db.query(
                    func.coalesce(func.sum(JournalEntry.debit), 0),
                    func.coalesce(func.sum(JournalEntry.credit), 0),
                )
                .join(Transaction, Transaction.id == JournalEntry.transaction_id)
                .filter(
                    JournalEntry.account_id == m.deposit_account_id,
                    Transaction.status.in_(BOOKED_STATUSES),
                    Transaction.transaction_date >= month_start,
                    Transaction.transaction_date <= month_end,
                )
                .one()
            )
            withdrawals, contributed = _q(row[0]), _q(row[1])
        members_out.append({
            "user_id": m.user_id,
            "full_name": m.user.full_name,
            "share_percent": _q(m.share_percent),
            "deposit_account_id": m.deposit_account_id,
            "share_amount": share,
            "own_withdrawals": withdrawals,
            "contributed": contributed,
            "recommended_transfer": _q(share + withdrawals - contributed),
        })

    return {
        "ledger_id": ledger_id,
        "month": f"{year:04d}-{month:02d}",
        "as_of": effective_as_of,
        "days_remaining": days_remaining,
        "month_complete": month_complete,
        "operating_account_id": settings.operating_account_id,
        "excluded_account_ids": sorted(excluded_ids),
        "totals": {
            "booked": booked_total,
            "booked_fixed": booked_fixed,
            "booked_variable": booked_variable,
            "excluded_booked": _q(excluded_booked),
            "planned_remaining": planned_total,
            "recurring_remaining": recurring_total,
            "variable_remaining": variable_remaining,
            "typical_variable_month": typical_variable,
            "forecast_total": forecast_total,
        },
        "planned": planned_lines,
        "recurring": recurring_lines,
        "members": members_out,
        "liquidity": _liquidity(db, settings),
    }


def _detect_period(past_months: list[int], target_idx: int) -> Optional[int]:
    """Return 1/2/3 for monthly/bimonthly/quarterly bills, else None.

    Monthly: seen in at least 3 of the last 4 months, or in at least 6 of the
    scanned history (a gap or two is tolerated). Bimonthly/quarterly: at least
    three occurrences with a constant gap.
    """
    recent = [m for m in past_months if m >= target_idx - 4]
    if len(recent) >= 3 or len(past_months) >= RECURRING_MIN_MONTHS_FOR_VARIABLE_BILL:
        return 1
    if len(past_months) >= 3:
        gaps = {b - a for a, b in zip(past_months, past_months[1:])}
        if len(gaps) == 1:
            gap = gaps.pop()
            if gap in (2, 3):
                return gap
    return None


def _covered_by_planned(key: str, amount: Decimal, planned_lines: list, planned_keys: list) -> bool:
    key_tokens = {t for t in key.split() if len(t) > 3}
    for line, pkey in zip(planned_lines, planned_keys):
        if abs(line["amount"] - amount) <= amount * PLANNED_AMOUNT_TOLERANCE:
            return True
        if key_tokens and key_tokens & {t for t in pkey.split() if len(t) > 3}:
            return True
    return False


def _liquidity(db: Session, settings: SettlementSettings) -> dict:
    def balance(account_id: int) -> Decimal:
        row = (
            db.query(
                func.coalesce(func.sum(JournalEntry.debit), 0),
                func.coalesce(func.sum(JournalEntry.credit), 0),
            )
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .filter(
                JournalEntry.account_id == account_id,
                Transaction.status.in_(BOOKED_STATUSES),
            )
            .one()
        )
        return Decimal(row[0]) - Decimal(row[1])

    operating_balance = _q(balance(settings.operating_account_id)) if settings.operating_account_id else None

    cards = []
    for ba in db.query(BankAccount).filter(
        BankAccount.ledger_id == settings.ledger_id,
        BankAccount.account_type == BankAccountType.CREDIT_CARD,
        BankAccount.is_active == True,  # noqa: E712
    ):
        cards.append({
            "bank_account_id": ba.id,
            "name": ba.name,
            "account_id": ba.account_id,
            "owed": _q(-balance(ba.account_id)),
        })

    return {
        "operating_balance": operating_balance,
        "credit_cards": cards,
        "credit_card_owed_total": _q(sum((c["owed"] for c in cards), ZERO)),
    }
