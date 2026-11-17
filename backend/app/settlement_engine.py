"""Monthly settlement calculation.

Forecasts a ledger's shared expenses for a month and splits them between the
configured members. Everything is driven by SettlementSettings; nothing here is
specific to a particular household.

Forecast for the month = booked expenses so far
                       + open planned transactions (registered invoices)
                       + recurring bills recognised from history, not yet seen
                         this month and not covered by a planned transaction
                       + loan instalments not yet paid this month
                       + pro-rated estimate of variable spending
                       - income the shared account earned itself
                       + principal repaid on shared debt

Loan instalments are kept apart from the recurring bills. Their amounts are
known exactly when an agreement is registered, and whether this month's has
been paid is read from the loan account, not from the payee name - a
refinanced loan arrives under a new name and would otherwise be counted next
to the old one it replaced.

Expenses are counted when booked (accrual view), so credit card purchases count
in the month they happen and the card settlement itself is never counted. That
is deliberate: a purchase made in May is charged to the members in May and the
invoice falls due in the middle of June, which leaves a month of slack for the
money to arrive. Billing on the cash date would put the contribution and the
due date in the same month and remove it.

Two things that are not expenses still belong in the split. Money the shared
account earns on its own - sales, cashback - reduces what the members have to
put in. Principal repaid on a shared loan is not a cost in the accounting
sense, but it is cash that has to leave the account, and the point of the
calculation is to get enough money in there. Repaying the credit card is
excluded from that, since those purchases were already counted as expenses. A
registered card statement is held out of the forecast for the same reason, and
reported on its own: it is the invoiced figure, not a new cost.
"""
import calendar
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
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
    SettlementFixedPayment,
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
# A liability without an agreement is taken for a loan when it has been paid
# down together with an interest expense in this many months
LOAN_MIN_INSTALMENT_MONTHS = 2
# Recent months whose instalments stand in for one not yet paid, when there
# is no agreement
LOAN_FALLBACK_MONTHS = 3

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
    # transactions seen, and how many of them were paid with a card
    tx_count: int = 0
    card_tx_count: int = 0


class SettlementDisabled(Exception):
    pass


def _card_account_ids(db: Session, ledger_id: int) -> set[int]:
    """GL accounts backed by a credit card.

    Paying the card down is not a shared outlay: the purchases behind it were
    counted as expenses when they were made. Every other liability is.
    """
    return {
        account_id for (account_id,) in db.query(BankAccount.account_id).filter(
            BankAccount.ledger_id == ledger_id,
            BankAccount.account_type == BankAccountType.CREDIT_CARD,
            BankAccount.account_id.isnot(None),
        )
    }


@dataclass
class _LoanHistory:
    # Transactions that pay down a loan, and the month index they fall in
    tx_ids: set = field(default_factory=set)
    # loan account -> month index -> cash paid (principal + interest + fees)
    paid: dict = field(default_factory=lambda: defaultdict(lambda: defaultdict(lambda: ZERO)))
    # loan account -> months with a repayment booked alongside an expense
    instalment_months: dict = field(default_factory=lambda: defaultdict(set))


def _loan_history(
    db: Session,
    ledger_id: int,
    since: date,
    until: date,
    card_ids: set[int],
    agreement_ids: set[int],
) -> tuple[set[int], _LoanHistory]:
    """Loan accounts and the instalments paid on them.

    A loan is a liability with an agreement, or one that has been paid down
    together with an interest expense in a couple of months. That keeps out
    liabilities like a suspense account, which are not instalments. Card
    accounts are never loans: paying the card is settled through the
    purchases behind it.
    """
    rows = (
        db.query(
            Transaction.id,
            Transaction.transaction_date,
            Account.account_type,
            JournalEntry.account_id,
            JournalEntry.debit,
            JournalEntry.credit,
        )
        .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
        .join(Account, Account.id == JournalEntry.account_id)
        .filter(
            Transaction.ledger_id == ledger_id,
            Transaction.status.in_(BOOKED_STATUSES),
            Transaction.transaction_date >= since,
            Transaction.transaction_date <= until,
            Transaction.id.in_(
                db.query(JournalEntry.transaction_id)
                .join(Account, Account.id == JournalEntry.account_id)
                .filter(
                    Account.ledger_id == ledger_id,
                    Account.account_type == AccountType.LIABILITY,
                )
            ),
        )
        .all()
    )
    by_tx: dict = defaultdict(list)
    for row in rows:
        by_tx[row[0]].append(row)

    hist = _LoanHistory()
    for tx_id, entries in by_tx.items():
        idx = _month_index(entries[0][1])
        expense = sum(
            (Decimal(d or 0) - Decimal(c or 0)
             for _, _, t, _, d, c in entries if t == AccountType.EXPENSE),
            ZERO,
        )
        repaid = [
            (acc, Decimal(d or 0) - Decimal(c or 0))
            for _, _, t, acc, d, c in entries
            if t == AccountType.LIABILITY and acc not in card_ids
            and Decimal(d or 0) > Decimal(c or 0)
        ]
        # Taking up a loan (a refinancing) credits a loan account; that is
        # not an instalment, and it is not told apart by anything else
        if not repaid or any(
            t == AccountType.LIABILITY and acc not in card_ids and Decimal(c or 0) > Decimal(d or 0)
            for _, _, t, acc, d, c in entries
        ):
            continue
        account_id, principal = repaid[0]
        hist.tx_ids.add(tx_id)
        hist.paid[account_id][idx] += principal + expense
        if expense > 0:
            hist.instalment_months[account_id].add(idx)

    loan_ids = set(agreement_ids) | {
        acc for acc, months in hist.instalment_months.items()
        if len(months) >= LOAN_MIN_INSTALMENT_MONTHS
    }
    # Repayments on liabilities that did not qualify stay ordinary transactions
    hist.tx_ids = {
        tx_id for tx_id in hist.tx_ids
        if any(r[3] in loan_ids for r in by_tx[tx_id])
    }
    return loan_ids, hist


def _agreement_due(fp: SettlementFixedPayment, target_idx: int) -> Optional[Decimal]:
    """The agreement's instalment for the month, or None when none falls due."""
    first_idx = _month_index(fp.first_month)
    if target_idx < first_idx:
        return None
    if fp.payment_count is not None and target_idx >= first_idx + fp.payment_count:
        return None
    if target_idx == first_idx and fp.first_amount is not None:
        return _q(fp.first_amount)
    return _q(fp.amount)


def _liability_balance(db: Session, account_id: int, as_of: date) -> Decimal:
    row = (
        db.query(
            func.coalesce(func.sum(JournalEntry.credit), 0),
            func.coalesce(func.sum(JournalEntry.debit), 0),
        )
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(
            JournalEntry.account_id == account_id,
            Transaction.status.in_(BOOKED_STATUSES),
            Transaction.transaction_date <= as_of,
        )
        .one()
    )
    return Decimal(row[0]) - Decimal(row[1])


def _side_flows(
    db: Session,
    ledger_id: int,
    since: date,
    until: date,
    skip: set[int],
    card_ids: set[int],
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """Income earned and loan principal repaid, per month index.

    Both sit outside the expense accounts the forecast is built from, and both
    change what the members owe: income downwards, principal upwards.
    """
    income: dict[int, Decimal] = defaultdict(lambda: ZERO)
    principal: dict[int, Decimal] = defaultdict(lambda: ZERO)

    # A repayment one member funds out of their own pocket is booked against
    # equity, not against the shared account, so it is not a shared outlay
    # however much it reduces the shared debt. The ordinary instalment never
    # touches equity, which is what tells the two apart.
    equity_tx = {
        tx_id for (tx_id,) in db.query(JournalEntry.transaction_id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .join(Account, Account.id == JournalEntry.account_id)
        .filter(
            Transaction.ledger_id == ledger_id,
            Transaction.transaction_date >= since,
            Transaction.transaction_date <= until,
            Account.account_type == AccountType.EQUITY,
        )
    }

    rows = (
        db.query(
            Transaction.id,
            Transaction.transaction_date,
            Account.account_type,
            JournalEntry.account_id,
            JournalEntry.debit,
            JournalEntry.credit,
        )
        .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
        .join(Account, Account.id == JournalEntry.account_id)
        .filter(
            Transaction.ledger_id == ledger_id,
            Transaction.status.in_(BOOKED_STATUSES),
            Transaction.transaction_date >= since,
            Transaction.transaction_date <= until,
            Account.account_type.in_((AccountType.REVENUE, AccountType.LIABILITY)),
        )
        .all()
    )
    for tx_id, tx_date, acc_type, account_id, debit, credit in rows:
        if account_id in skip:
            continue
        idx = _month_index(tx_date)
        if acc_type == AccountType.REVENUE:
            income[idx] += Decimal(credit or 0) - Decimal(debit or 0)
        elif account_id not in card_ids and tx_id not in equity_tx:
            principal[idx] += Decimal(debit or 0) - Decimal(credit or 0)
    return income, principal


def _carry(
    db: Session,
    settings: SettlementSettings,
    target_idx: int,
    excluded_ids: set[int],
    deposit_ids: set[int],
    card_ids: set[int],
) -> tuple[dict[int, Decimal], Optional[date]]:
    """Each member's running over- or underpayment, in closed months.

    A member who paid 1 000 too little in September owes it in October; the
    month is not a clean slate. Only months that have closed are counted, and
    only from the configured start - what happened before that is taken to be
    settled between the members already.

    Positive means the member has paid more than their share and the next
    recommendation is reduced by it.
    """
    start = settings.carry_start
    if start is None:
        return {m.user_id: ZERO for m in settings.members}, None

    start_idx = _month_index(start)
    if start_idx >= target_idx:
        return {m.user_id: ZERO for m in settings.members}, start

    # Closed months only: the target month is still being forecast
    last_end = _month_bounds(*_month_from_index(target_idx - 1))[1]
    skip = excluded_ids | deposit_ids

    expenses: dict[int, Decimal] = defaultdict(lambda: ZERO)
    rows = (
        db.query(
            Transaction.transaction_date,
            (JournalEntry.debit - JournalEntry.credit).label("amount"),
        )
        .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
        .join(Account, Account.id == JournalEntry.account_id)
        .filter(
            Transaction.ledger_id == settings.ledger_id,
            Transaction.status.in_(BOOKED_STATUSES),
            Transaction.transaction_date >= start,
            Transaction.transaction_date <= last_end,
            Account.account_type == AccountType.EXPENSE,
            JournalEntry.account_id.notin_(excluded_ids) if excluded_ids else True,
        )
        .all()
    )
    for tx_date, amount in rows:
        expenses[_month_index(tx_date)] += Decimal(amount or 0)

    income, principal = _side_flows(
        db, settings.ledger_id, start, last_end, skip, card_ids,
    )

    net_cost = {
        idx: expenses.get(idx, ZERO) - income.get(idx, ZERO) + principal.get(idx, ZERO)
        for idx in range(start_idx, target_idx)
    }

    out: dict[int, Decimal] = {}
    for m in settings.members:
        owed = sum(
            (cost * Decimal(m.share_percent) / Decimal(100) for cost in net_cost.values()),
            ZERO,
        )
        paid = ZERO
        if m.deposit_account_id:
            row = (
                db.query(
                    func.coalesce(func.sum(JournalEntry.credit), 0),
                    func.coalesce(func.sum(JournalEntry.debit), 0),
                )
                .join(Transaction, Transaction.id == JournalEntry.transaction_id)
                .filter(
                    JournalEntry.account_id == m.deposit_account_id,
                    Transaction.status.in_(BOOKED_STATUSES),
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= last_end,
                )
                .one()
            )
            paid = Decimal(row[0]) - Decimal(row[1])
        out[m.user_id] = _q(paid - owed)
    return out, start


def calculate_settlement(
    db: Session,
    settings: SettlementSettings,
    year: int,
    month: int,
    as_of: Optional[date] = None,
    with_timeline: bool = True,
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

    card_ids = _card_account_ids(db, ledger_id)
    agreements = list(getattr(settings, "fixed_payments", []) or [])
    loan_ids, loans = _loan_history(
        db, ledger_id, history_start, effective_as_of, card_ids,
        {fp.account_id for fp in agreements},
    )

    card_tx_ids = {
        tx_id for (tx_id,) in db.query(JournalEntry.transaction_id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .filter(
            Transaction.ledger_id == ledger_id,
            Transaction.transaction_date >= history_start,
            Transaction.transaction_date <= month_end,
            JournalEntry.account_id.in_(card_ids),
        )
    } if card_ids else set()

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
    loan_booked = ZERO
    seen_tx_month: set[tuple[str, int]] = set()

    for tx_id, tx_date, description, account_id, amount in rows:
        amount = Decimal(amount or 0)
        idx = _month_index(tx_date)
        if account_id in excluded_ids:
            if idx == target_idx:
                excluded_booked += amount
            continue
        # Interest and fees on an instalment belong to the loan, which is
        # forecast from its agreement; kept out of the recurring bills and
        # the variable history
        if tx_id in loans.tx_ids:
            if idx == target_idx:
                loan_booked += amount
            continue

        key = normalize_key(description)
        month_totals[idx] += amount
        tx_amount_by_key_month[(key, idx)] += amount

        st = stats[key]
        st.monthly_totals[idx] += amount
        if (str(tx_id), idx) not in seen_tx_month:
            seen_tx_month.add((str(tx_id), idx))
            st.monthly_counts[idx] += 1
            st.tx_count += 1
            if tx_id in card_tx_ids:
                st.card_tx_count += 1
        st.monthly_first_day[idx] = min(st.monthly_first_day.get(idx, 31), tx_date.day)
        if not st.sample_description:
            st.sample_description = description

        if tx_id in matched_tx_ids:
            invoice_amount_by_key_month[(key, idx)] += amount

    booked_total = _q(month_totals.get(target_idx, ZERO) + loan_booked)

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
            "by_card": st.card_tx_count * 2 > st.tx_count,
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
    card_statement_lines = []
    loan_invoices = []
    for p in open_plans:
        if p.suggested_account_id in excluded_ids:
            continue
        if month_complete:
            # Nothing more will be paid in a closed month; unmatched plans
            # there are stale, not upcoming
            continue
        line = {
            "planned_transaction_id": p.id,
            "receipt_id": p.receipt_id,
            "description": p.description,
            "expected_date": p.expected_date,
            "amount": _q(p.amount),
            "overdue": p.expected_date < effective_as_of,
        }
        # A card statement is not a cost of its own. The purchases behind it
        # were counted as expenses when they were made, in the month they were
        # made, so counting the statement too would charge the members twice:
        # once in the month of the purchase and again in the month the invoice
        # falls due. It is also already in the liquidity figure as the card
        # balance, so leaving it in open_invoices would subtract it twice over.
        if p.suggested_account_id in card_ids:
            card_statement_lines.append(line)
        elif p.suggested_account_id in loan_ids:
            line["account_id"] = p.suggested_account_id
            loan_invoices.append(line)
        else:
            planned_lines.append(line)
    planned_total = _q(sum((l["amount"] for l in planned_lines), ZERO))
    card_invoiced = _q(sum((l["amount"] for l in card_statement_lines), ZERO))

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
            "by_card": info["by_card"],
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

    booked_fixed = _q(fixed_part(target_idx) + loan_booked)
    booked_variable = _q(booked_total - booked_fixed)
    variable_remaining = ZERO if month_complete else _q(
        typical_variable * Decimal(days_remaining) / Decimal(days_in_month)
    )

    # ------------------------------------------------------------------
    # Income and loan principal: outside the expense accounts, inside the split
    # ------------------------------------------------------------------
    deposit_ids = {m.deposit_account_id for m in settings.members if m.deposit_account_id}
    side_income, side_principal = _side_flows(
        db, ledger_id, history_start, month_end,
        excluded_ids | deposit_ids, card_ids,
    )
    income_booked = _q(side_income.get(target_idx, ZERO))
    principal_booked = _q(side_principal.get(target_idx, ZERO))

    loan_lines = _loan_lines(
        db, agreements, loan_ids, loans, loan_invoices,
        target_idx, month_start, month_end, effective_as_of, month_complete,
    )
    loan_remaining = _q(sum(
        (l["amount"] for l in loan_lines if l["status"] != "PAID"), ZERO,
    ))

    forecast_total = _q(
        booked_total + planned_total + recurring_total + loan_remaining
        + variable_remaining - income_booked + principal_booked
    )

    carry_by_user, carry_from = _carry(
        db, settings, target_idx, excluded_ids, deposit_ids, card_ids,
    )

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
        carry = carry_by_user.get(m.user_id, ZERO)
        members_out.append({
            "user_id": m.user_id,
            "full_name": m.user.full_name,
            "share_percent": _q(m.share_percent),
            "deposit_account_id": m.deposit_account_id,
            "share_amount": share,
            "own_withdrawals": withdrawals,
            "contributed": contributed,
            "carry_in": carry,
            "liquidity_topup": ZERO,
            "recommended_transfer": _q(share + withdrawals - contributed - carry),
        })

    liquidity = _liquidity(db, settings, members_out, planned_total, card_invoiced)
    if with_timeline and month_start <= as_of <= month_end and settings.operating_account_id:
        next_year, next_month = _month_from_index(target_idx + 1)
        following = calculate_settlement(
            db, settings, next_year, next_month, as_of=as_of, with_timeline=False,
        )

        def timeline():
            return _cash_timeline(
                db, settings, as_of, month_start, month_end,
                members_out, planned_lines, recurring_lines, loan_lines,
                variable_remaining, card_invoiced, liquidity, following,
            )

        # The share of the month's costs is not always enough cash on the
        # right day: a large card invoice and a loan can fall due before the
        # next deposit. Raise this month's contributions by what is missing,
        # split by share. The overpayment is carried into next month as
        # usual, where this same check holds it back for as long as the gap
        # is there - in effect a standing buffer, returned once it is not.
        min_balance = Decimal(settings.min_balance or 0)
        tl = timeline()
        need = min_balance - tl["lowest_balance"]
        topup_total = ZERO
        if need > 0:
            for m in members_out:
                rec = m["recommended_transfer"]
                # A member who is ahead holds back nothing: the deposit has
                # to rise by the full share of the gap
                target = max(rec, ZERO) + (need * m["share_percent"] / Decimal(100)).quantize(
                    Decimal("1"), rounding=ROUND_CEILING)
                if target > rec:
                    m["liquidity_topup"] = _q(target - rec)
                    m["recommended_transfer"] = _q(target)
                    topup_total += m["liquidity_topup"]
            liquidity = _liquidity(db, settings, members_out, planned_total, card_invoiced)
            tl = timeline()
        tl["min_balance"] = _q(min_balance)
        tl["topup_total"] = _q(topup_total)
        liquidity["timeline"] = tl

    return {
        "ledger_id": ledger_id,
        "month": f"{year:04d}-{month:02d}",
        "as_of": effective_as_of,
        "days_remaining": days_remaining,
        "month_complete": month_complete,
        "operating_account_id": settings.operating_account_id,
        "excluded_account_ids": sorted(excluded_ids),
        "carry_from": carry_from,
        "totals": {
            "booked": booked_total,
            "booked_fixed": booked_fixed,
            "booked_variable": booked_variable,
            "excluded_booked": _q(excluded_booked),
            "planned_remaining": planned_total,
            # Loan instalments are fixed withdrawals too; kept in this
            # figure so older clients that sum the parts still add up
            "recurring_remaining": _q(recurring_total + loan_remaining),
            "loan_remaining": loan_remaining,
            "variable_remaining": variable_remaining,
            "typical_variable_month": typical_variable,
            "income_booked": income_booked,
            "debt_principal": principal_booked,
            "forecast_total": forecast_total,
        },
        "planned": planned_lines,
        "card_statements": card_statement_lines,
        "recurring": recurring_lines,
        "loans": loan_lines,
        "members": members_out,
        "liquidity": liquidity,
    }


def _loan_lines(
    db: Session,
    agreements: list,
    loan_ids: set[int],
    loans: _LoanHistory,
    loan_invoices: list,
    target_idx: int,
    month_start: date,
    month_end: date,
    as_of: date,
    month_complete: bool,
) -> list[dict]:
    """This month's instalment on every loan, paid or still to come.

    An agreement gives the amount; a registered invoice on the loan account
    overrides it, being the lender's own figure. A loan with neither falls
    back on its recent instalments for as long as there is debt left.
    """
    by_account = {fp.account_id: fp for fp in agreements}
    invoices = defaultdict(list)
    for inv in loan_invoices:
        invoices[inv["account_id"]].append(inv)

    lines = []
    for account_id in sorted(loan_ids):
        fp = by_account.get(account_id)
        paid = loans.paid.get(account_id, {}).get(target_idx)
        line = {
            "fixed_payment_id": fp.id if fp else None,
            "account_id": account_id,
            "name": fp.name if fp else None,
            "due_date": None,
            "amount": ZERO,
            "status": "EXPECTED",
            "source": "AGREEMENT" if fp else "HISTORY",
        }
        if fp:
            due = _agreement_due(fp, target_idx)
            if due is None and not paid and not invoices[account_id]:
                continue
            line["amount"] = due or ZERO
            day = min(fp.due_day, (month_end - month_start).days + 1)
            line["due_date"] = month_start.replace(day=day)
        if paid:
            line.update(amount=_q(paid), status="PAID")
        elif invoices[account_id]:
            inv = invoices[account_id]
            line.update(
                amount=_q(sum((i["amount"] for i in inv), ZERO)),
                status="INVOICED",
                source="INVOICE",
                due_date=inv[0]["expected_date"],
                planned_transaction_id=inv[0]["planned_transaction_id"],
            )
            if not line["name"]:
                line["name"] = inv[0]["description"]
        elif fp:
            if month_complete:
                continue
        else:
            # No agreement: the recent instalments stand in, until the loan
            # is paid off or replaced
            if month_complete or _liability_balance(db, account_id, as_of) <= 0:
                continue
            recent = [
                float(loans.paid[account_id].get(target_idx - i, ZERO))
                for i in range(1, LOAN_FALLBACK_MONTHS + 1)
            ]
            recent = [v for v in recent if v > 0]
            if not recent:
                continue
            line["amount"] = _q(statistics.median(recent))
        if line["amount"] <= 0:
            continue
        lines.append(line)
    for line in lines:
        if not line["name"]:
            acc = db.get(Account, line["account_id"])
            line["name"] = f"{acc.account_number} {acc.account_name}" if acc else "Lån"
    lines.sort(key=lambda l: (l["due_date"] or month_end, l["account_id"]))
    return lines


def _on_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _cash_timeline(
    db: Session,
    settings: SettlementSettings,
    as_of: date,
    month_start: date,
    month_end: date,
    members_out: list,
    planned_lines: list,
    recurring_lines: list,
    loan_lines: list,
    variable_remaining: Decimal,
    card_invoiced: Decimal,
    liquidity: dict,
    following: dict,
) -> dict:
    """Balance day by day until the end of next month.

    The month-end figure says whether the money is there eventually; this says
    whether it is there on the day each payment is drawn. The accounts loans
    are drawn from count together with the operating account, since they are
    topped up from it just before the draw.

    Card purchases leave the account with the invoice, not on the day they are
    made: everything owed on the card now, plus the purchases still expected
    this month, falls due on next month's due day. Anything overdue is put on
    today, and outflows go before inflows on the same day, so the figure errs
    on the cautious side.
    """
    ledger_id = settings.ledger_id
    account_ids = sorted({settings.operating_account_id} | {
        fp.paid_from_account_id for fp in settings.fixed_payments
        if fp.paid_from_account_id
    })
    start_balance = ZERO
    for account_id in account_ids:
        row = (
            db.query(
                func.coalesce(func.sum(JournalEntry.debit), 0),
                func.coalesce(func.sum(JournalEntry.credit), 0),
            )
            .join(Transaction, Transaction.id == JournalEntry.transaction_id)
            .filter(
                JournalEntry.account_id == account_id,
                Transaction.status.in_(BOOKED_STATUSES),
                Transaction.transaction_date <= as_of,
            )
            .one()
        )
        start_balance += Decimal(row[0]) - Decimal(row[1])

    next_start = month_end + timedelta(days=1)
    next_end = _month_bounds(next_start.year, next_start.month)[1]
    events = []
    assumed = []

    def add(day: Optional[date], description: str, amount: Decimal, kind: str):
        amount = _q(amount)
        if amount == 0:
            return
        day = max(day or as_of, as_of)
        if day > next_end:
            return
        events.append({"date": day, "description": description, "amount": amount, "kind": kind})

    deposit_day = {m.user_id: m.deposit_day for m in settings.members}

    def contributions(members: list, year: int, month: int, field_name: str, this_month: bool):
        for m in members:
            amount = Decimal(m[field_name])
            if amount <= 0:
                continue
            day = deposit_day.get(m["user_id"])
            if day is None:
                if this_month:
                    assumed.append(m["full_name"])
                when = as_of if this_month else date(year, month, 1)
            else:
                when = _on_day(year, month, day)
            add(when, f"Innskudd {m['full_name']}", amount, "DEPOSIT")

    # This month
    contributions(members_out, month_start.year, month_start.month, "recommended_transfer", True)
    for line in loan_lines:
        if line["status"] != "PAID":
            add(line["due_date"], line["name"], -line["amount"], "LOAN")
    for line in planned_lines:
        add(line["expected_date"], line["description"], -line["amount"], "INVOICE")
    card_recurring = ZERO
    for line in recurring_lines:
        if line["by_card"]:
            card_recurring += line["amount"]
        else:
            add(_on_day(month_start.year, month_start.month, line["expected_day"]),
                line["description"], -line["amount"], "RECURRING")

    # Credit card: this month's invoice if it has not been paid yet, then
    # next month's, which holds everything charged until the month ends
    card_ids = {c["account_id"] for c in liquidity["credit_cards"]}
    owed = Decimal(liquidity["credit_card_owed_total"])
    if card_ids:
        card_paid_this_month = db.query(JournalEntry.id).join(
            Transaction, Transaction.id == JournalEntry.transaction_id,
        ).filter(
            Transaction.ledger_id == ledger_id,
            Transaction.status.in_(BOOKED_STATUSES),
            Transaction.transaction_date >= month_start,
            Transaction.transaction_date <= as_of,
            JournalEntry.account_id.in_(card_ids),
            JournalEntry.debit > 0,
            Transaction.id.in_(
                db.query(JournalEntry.transaction_id).filter(JournalEntry.account_id.in_(account_ids))
            ),
        ).first() is not None
        next_bill = owed + variable_remaining + card_recurring
        if not card_paid_this_month:
            this_bill = card_invoiced if card_invoiced > 0 else owed
            add(_on_day(month_start.year, month_start.month, settings.card_due_day),
                "Kredittkortfaktura", -this_bill, "CARD")
            next_bill -= this_bill
        add(_on_day(next_start.year, next_start.month, settings.card_due_day),
            "Kredittkortfaktura", -max(next_bill, ZERO), "CARD")

    # Next month
    contributions(following["members"], next_start.year, next_start.month, "share_amount", False)
    for line in following["loans"]:
        if line["status"] != "PAID":
            add(line["due_date"], line["name"], -line["amount"], "LOAN")
    for line in following["planned"]:
        add(line["expected_date"], line["description"], -line["amount"], "INVOICE")
    for line in following["recurring"]:
        if not line["by_card"]:
            add(_on_day(next_start.year, next_start.month, line["expected_day"]),
                line["description"], -line["amount"], "RECURRING")

    events.sort(key=lambda e: (e["date"], e["amount"] > 0))
    balance = _q(start_balance)
    lowest, lowest_date = balance, as_of
    shortfall = None
    for e in events:
        balance = _q(balance + e["amount"])
        e["balance"] = balance
        if balance < lowest:
            lowest, lowest_date = balance, e["date"]
        if balance < 0 and shortfall is None:
            shortfall = e

    return {
        "start_date": as_of,
        "end_date": next_end,
        "account_ids": account_ids,
        "start_balance": _q(start_balance),
        "events": events,
        "lowest_balance": lowest,
        "lowest_date": lowest_date,
        "shortfall_date": shortfall["date"] if shortfall else None,
        "shortfall_description": shortfall["description"] if shortfall else None,
        "shortfall_amount": -shortfall["balance"] if shortfall else None,
        "assumed_deposit_days": assumed,
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


def _liquidity(
    db: Session,
    settings: SettlementSettings,
    members_out: list,
    open_invoices: Decimal,
    card_invoiced: Decimal = ZERO,
) -> dict:
    """Cash position, read on the assumption that everyone pays their share.

    The bank balance on its own answers the wrong question. Part of it is owed
    to the credit card company in the middle of next month and part of it is
    spoken for by invoices already registered, while the contributions still
    outstanding are money that is going to arrive. What is left over when all
    three are accounted for is the only figure that is free to spend.
    """
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

    card_total = _q(sum((c["owed"] for c in cards), ZERO))
    outstanding = _q(sum(
        (m["recommended_transfer"] for m in members_out
         if m["recommended_transfer"] > 0), ZERO,
    ))
    expected = None
    covers_card = None
    if operating_balance is not None:
        expected = _q(operating_balance + outstanding - card_total - open_invoices)
        covers_card = operating_balance + outstanding >= card_total

    return {
        "operating_balance": operating_balance,
        "credit_cards": cards,
        "credit_card_owed_total": card_total,
        # What the card company has actually invoiced, when a statement is
        # registered. The balance above is larger: it also holds the purchases
        # made since the statement closed, which fall due a month later. The
        # figures below keep using the balance, which is the conservative read.
        "card_invoiced": _q(card_invoiced),
        "open_invoices": _q(open_invoices),
        "outstanding_contributions": outstanding,
        "expected_available": expected,
        "covers_card": covers_card,
        "card_due_day": settings.card_due_day,
    }
