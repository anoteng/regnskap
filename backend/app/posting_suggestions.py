"""Suggest which account to post a bank-synced draft to, from earlier postings.

The same merchant shows up with different wrapping depending on how it was
paid — "Vipps*Skjoershammer Brygg Oslo          NO" from the account and
"CRV*Vipps*Skjoershammer Brygg    CRV*   LT" from the card — so vendors are
grouped by the normalised key the settlement engine already uses.
"""
from collections import defaultdict
from datetime import date
from typing import Dict, Iterable, List

from sqlalchemy.orm import Session

from .models import (
    Account,
    BankAccount,
    JournalEntry,
    Transaction,
    TransactionStatus,
)
from .settlement_engine import normalize_key

BOOKED = (TransactionStatus.POSTED, TransactionStatus.RECONCILED)

# How far back to learn from, and how many alternatives to offer per vendor
HISTORY_MONTHS = 24
MAX_SUGGESTIONS = 3
# normalize_key keeps the first three words, and card statements truncate
# merchant names differently ("… Brygg Oslo" vs "… Brygg"). When the full key
# finds nothing, fall back to the first two words.
PREFIX_TOKENS = 2


def _prefix(key: str) -> str:
    return " ".join(key.split()[:PREFIX_TOKENS])


def suggestions_for_drafts(
    db: Session,
    ledger_id: int,
    drafts: Iterable[Transaction],
) -> Dict[int, List[dict]]:
    """Ranked counter-account suggestions per draft transaction id.

    Built from one pass over the ledger's history rather than a query per
    draft, so a full queue costs the same as a single item.
    """
    drafts = list(drafts)
    if not drafts:
        return {}

    wanted = {normalize_key(d.description) for d in drafts}
    wanted.discard("")
    if not wanted:
        return {}
    wanted_prefixes = {_prefix(k) for k in wanted}

    # Accounts the bank sync itself posts to are never the answer
    bank_linked = {
        account_id for (account_id,) in db.query(BankAccount.account_id).filter(
            BankAccount.ledger_id == ledger_id
        )
    }

    today = date.today()
    month_index = today.year * 12 + (today.month - 1) - HISTORY_MONTHS
    cutoff = date(month_index // 12, month_index % 12 + 1, 1)

    rows = (
        db.query(
            Transaction.description,
            Transaction.transaction_date,
            Account.id,
            Account.account_number,
            Account.account_name,
        )
        .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
        .join(Account, Account.id == JournalEntry.account_id)
        .filter(
            Transaction.ledger_id == ledger_id,
            Transaction.status.in_(BOOKED),
            Transaction.transaction_date >= cutoff,
            Account.is_active == True,  # noqa: E712
        )
        .all()
    )

    # vendor key -> account id -> [count, last used, number, name]
    tally: Dict[str, Dict[int, list]] = defaultdict(dict)
    prefix_tally: Dict[str, Dict[int, list]] = defaultdict(dict)

    def record(bucket: Dict[int, list], account_id: int, tx_date, number, name):
        entry = bucket.get(account_id)
        if entry is None:
            bucket[account_id] = [1, tx_date, number, name]
        else:
            entry[0] += 1
            entry[1] = max(entry[1], tx_date)

    for description, tx_date, account_id, number, name in rows:
        if account_id in bank_linked:
            continue
        key = normalize_key(description)
        if not key:
            continue
        if key in wanted:
            record(tally[key], account_id, tx_date, number, name)
        prefix = _prefix(key)
        if prefix in wanted_prefixes:
            record(prefix_tally[prefix], account_id, tx_date, number, name)

    result: Dict[int, List[dict]] = {}
    for draft in drafts:
        key = normalize_key(draft.description)
        candidates = tally.get(key) or prefix_tally.get(_prefix(key))
        if not candidates:
            continue
        # Most used first, then most recently used
        ranked = sorted(
            candidates.items(),
            key=lambda item: (item[1][0], item[1][1]),
            reverse=True,
        )[:MAX_SUGGESTIONS]
        result[draft.id] = [
            {
                "account_id": account_id,
                "account_number": number,
                "account_name": name,
                "times_used": count,
                "last_used": last_used,
            }
            for account_id, (count, last_used, number, name) in ranked
        ]
    return result
