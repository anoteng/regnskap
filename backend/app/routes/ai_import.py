"""Transactions read by AI from pasted text or screenshots.

For accounts the bank will not share over PSD2 -- DNB's credit card is the
case in point -- the user can paste the rows of the bank's own Excel export,
or a screenshot from the online or mobile bank, and have the model read them.

Two steps, so nothing reaches the books unseen:

1. preview: the model reads the rows; the server marks each one as new,
   duplicate, possible duplicate or reserved. Nothing is stored.
2. commit: the rows the user kept are stored as DRAFT, for the posting queue.

Duplicates are judged here, never by the model, and never by the text: the
same purchase reads "VINMONOPOLET STROMMEN" in the export and "Vinmonopolet"
in the app. Date, direction and amount decide, counted, so three identical
bus tickets against two already in the books leaves one new.
"""
import base64
import io
import json
import re
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from ..auth import get_current_active_user, require_ledger_write
from ..models import (
    Account, AccountType, BankAccount, ImportLog, JournalEntry, Ledger,
    Transaction, TransactionSource, TransactionStatus, User,
)
from ..subscriptions import resolve_ai_api_key
from .receipts import SUPPORTED_IMAGE_TYPES, _response_text, increment_ai_usage

router = APIRouter(prefix="/ai-import", tags=["ai-import"])

MAX_TEXT = 60_000
MAX_IMAGES = 6
MAX_IMAGE_BYTES = 15 * 1024 * 1024
# A booking can land a few days off the date shown elsewhere; within this
# window a same-amount entry is worth a question, not an answer
NEAR_DAYS = 3
RESERVED = re.compile(r"\s*\(?\breserv(?:ert|ed)\b(?:\s+transaksjon)?\)?\s*", re.IGNORECASE)


def _image_blocks(data: bytes) -> List[dict]:
    """The screenshot as image blocks the model can read.

    The API scales every image to about a megapixel. A phone screenshot
    survives that; a long scrolling capture does not -- 1080x8000 would come
    out a few hundred pixels wide and unreadable. Tall images are cut into
    slices of phone-screen proportions instead, overlapping a little so no
    row is lost at a cut.
    """
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if w > 1400:
        img = img.resize((1400, int(h * 1400 / w)), Image.LANCZOS)
        w, h = img.size

    step = int(w * 1.8)
    overlap = int(w * 0.15)
    slices = []
    top = 0
    while True:
        bottom = min(h, top + step)
        slices.append(img.crop((0, top, w, bottom)))
        if bottom >= h:
            break
        top = bottom - overlap

    blocks = []
    for part in slices:
        buf = io.BytesIO()
        part.save(buf, format="JPEG", quality=85)
        blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(buf.getvalue()).decode(),
            },
        })
    return blocks


def _prompt(account: Account, text: str, sliced: bool) -> str:
    kind = (
        "a credit card" if account.account_type == AccountType.LIABILITY
        else "a bank account"
    )
    today = date.today().isoformat()
    parts = [
        f"""The user has given you transactions from {kind} ("{account.account_name}"), \
as text pasted from the bank's export and/or screenshots of the online or mobile bank. \
Read every transaction row.

Today is {today}. Where a row shows no year, use the most recent year that does not put \
the date in the future.

For each transaction give:
- "date": YYYY-MM-DD, the date shown on the row
- "description": the text as the bank shows it, without any reserved/pending marker
- "amount": the amount in the account's currency (NOK), always positive, as a number
- "direction": "out" when money is spent or leaves (purchase, withdrawal, fee, interest \
charged), "in" when money comes in (payment to the card, refund, discount, deposit, salary)
- "reserved": true when the row is not yet booked: marked "Reservert", "Reservert \
transaksjon", "Ikke bokført", "Pending", listed under a reserved/pending heading, or shown \
without a booking date where booked rows have one. Otherwise false.

When a row shows an amount in a foreign currency and also in NOK, use the NOK amount.
When the text has separate columns for money in and money out ("Inn"/"Ut"), the column \
decides the direction. A minus sign means out, unless the columns say otherwise.
Skip headers, balances, sums, available credit and anything that is not a transaction.
Give every row exactly once, in the order shown, even when two rows look identical: \
identical purchases on the same day are real.""",
    ]
    if sliced:
        parts.append(
            "Some images are consecutive slices of one long screenshot, cut with a small "
            "overlap. A row that appears at the bottom of one slice and again at the top of "
            "the next is the same row: give it once."
        )
    if text:
        parts.append(f"<pasted>\n{text}\n</pasted>")
    parts.append(
        'Answer with JSON only: {"transactions": [ ... ], "notes": "anything the user '
        'should know, in Norwegian, or null"}'
    )
    return "\n\n".join(parts)


def _parse(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return json.loads(raw)


def _clean_rows(found: list) -> List[dict]:
    """The model's rows, checked and normalised. Anything unreadable is dropped."""
    rows = []
    for item in found or []:
        try:
            day = date.fromisoformat(str(item["date"]))
            amount = abs(Decimal(str(item["amount"]))).quantize(Decimal("0.01"))
        except (KeyError, ValueError, InvalidOperation):
            continue
        if amount == 0:
            continue
        direction = "in" if str(item.get("direction")).lower() == "in" else "out"
        description = str(item.get("description") or "").strip()
        # Belt and braces: the export marks a reservation in the text itself
        reserved = bool(item.get("reserved")) or bool(RESERVED.search(description))
        description = RESERVED.sub(" ", description).strip(" ,") or "Transaksjon"
        rows.append({
            "date": day,
            "description": description[:500],
            "amount": amount,
            "direction": direction,
            "reserved": reserved,
        })
    return rows


def _bank_account(db: Session, ledger: Ledger, bank_account_id: int) -> BankAccount:
    bank_account = db.query(BankAccount).filter(
        BankAccount.id == bank_account_id,
        BankAccount.ledger_id == ledger.id,
    ).first()
    if not bank_account or not bank_account.account_id:
        raise HTTPException(status_code=404, detail="Fant ikke bankkontoen.")
    return bank_account


def _side(direction: str) -> str:
    # In raises an asset and lowers a card's debt: debit either way.
    # Out is the mirror image. The account type needs no say.
    return "debit" if direction == "in" else "credit"


def _existing(db: Session, account_id: int, first: date, last: date) -> List[dict]:
    """What the account already holds around the given dates, drafts included."""
    found = db.query(
        Transaction.id, Transaction.transaction_date, Transaction.description,
        JournalEntry.debit, JournalEntry.credit,
    ).join(JournalEntry, JournalEntry.transaction_id == Transaction.id).filter(
        JournalEntry.account_id == account_id,
        Transaction.transaction_date >= first - timedelta(days=NEAR_DAYS),
        Transaction.transaction_date <= last + timedelta(days=NEAR_DAYS),
    ).all()
    entries = []
    for tx_id, day, description, debit, credit in found:
        debit, credit = Decimal(debit or 0), Decimal(credit or 0)
        if debit == credit:
            continue
        side = "debit" if debit > credit else "credit"
        entries.append({
            "id": tx_id, "date": day, "description": description,
            "side": side, "amount": abs(debit - credit),
        })
    return entries


def _judge(rows: List[dict], existing: List[dict]) -> None:
    """Mark each row new, duplicate, possible or reserved, in place.

    Exact matches are settled first across the whole batch, so a near match
    never steals the entry an exact one needed.
    """
    pool = {}
    for entry in existing:
        pool.setdefault((entry["date"], entry["side"], entry["amount"]), []).append(entry)

    for row in rows:
        row["match"] = None
        if row["reserved"]:
            row["status"] = "reserved"
            continue
        held = pool.get((row["date"], _side(row["direction"]), row["amount"]))
        if held:
            row["status"] = "duplicate"
            row["match"] = held.pop(0)
        else:
            row["status"] = "new"

    for row in rows:
        if row["status"] != "new":
            continue
        side = _side(row["direction"])
        for (day, s, amount), held in pool.items():
            if held and s == side and amount == row["amount"] \
                    and abs((day - row["date"]).days) <= NEAR_DAYS:
                row["status"] = "possible"
                row["match"] = held.pop(0)
                break


def _out(row: dict) -> dict:
    match = row.get("match")
    return {
        "date": row["date"].isoformat(),
        "description": row["description"],
        "amount": str(row["amount"]),
        "direction": row["direction"],
        "status": row["status"],
        "match": {
            "transaction_id": match["id"],
            "date": match["date"].isoformat(),
            "description": match["description"],
        } if match else None,
    }


@router.post("/preview")
async def preview(
    bank_account_id: int = Form(...),
    text: str = Form(""),
    files: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(require_ledger_write),
    settings=Depends(get_settings),
):
    """Read transactions from pasted text and/or screenshots. Stores nothing.

    Each row comes back with a status:
    - new: not in the books
    - duplicate: the account already has this date, direction and amount
    - possible: the same amount and direction a few days off; the user decides
    - reserved: not yet booked by the bank, never imported
    """
    api_key = resolve_ai_api_key(current_user, db, settings.anthropic_api_key)
    bank_account = _bank_account(db, current_ledger, bank_account_id)
    account = db.query(Account).get(bank_account.account_id)

    text = (text or "").strip()
    if len(text) > MAX_TEXT:
        raise HTTPException(status_code=400, detail="Teksten er for lang. Del den opp.")
    files = [f for f in files if f and f.filename]
    if len(files) > MAX_IMAGES:
        raise HTTPException(status_code=400, detail=f"Maks {MAX_IMAGES} bilder om gangen.")
    if not text and not files:
        raise HTTPException(status_code=400, detail="Lim inn tekst eller legg ved et skjermbilde.")

    images = []
    for upload in files:
        mime = (upload.content_type or "").lower()
        if mime not in SUPPORTED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Skjermbilder må være JPEG, PNG, GIF eller WebP.")
        data = await upload.read()
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Et av bildene er for stort.")
        try:
            images.extend(_image_blocks(data))
        except Exception:
            raise HTTPException(status_code=400, detail="Kunne ikke lese et av bildene.")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=16000,
            messages=[{
                "role": "user",
                "content": images + [{
                    "type": "text",
                    "text": _prompt(account, text, len(images) > len(files)),
                }],
            }],
        )
        result = _parse(_response_text(message))
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="AI returnerte ugyldig data. Prøv igjen.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI-tolkningen feilet: {e}")

    increment_ai_usage(current_user, db)

    rows = _clean_rows(result.get("transactions"))
    if rows:
        days = [r["date"] for r in rows]
        _judge(rows, _existing(db, account.id, min(days), max(days)))

    return {
        "bank_account_id": bank_account.id,
        "account": {"number": account.account_number, "name": account.account_name},
        "notes": result.get("notes"),
        "transactions": [_out(r) for r in rows],
    }


class CommitRow(BaseModel):
    date: date
    description: str = Field(..., min_length=1, max_length=500)
    amount: Decimal = Field(..., gt=0)
    direction: str = Field(..., pattern="^(in|out)$")
    # The user kept a row the preview called a duplicate: import it as is
    force: bool = False


class CommitRequest(BaseModel):
    bank_account_id: int
    transactions: List[CommitRow] = Field(..., max_length=1000)


@router.post("/commit")
def commit(
    request: CommitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(require_ledger_write),
):
    """Store the rows the user kept as DRAFT transactions.

    Duplicates are counted again first, so a second click or an import made
    in the meantime does not double anything. Rows marked force skip that.
    """
    bank_account = _bank_account(db, current_ledger, request.bank_account_id)
    account_id = bank_account.account_id

    rows = [r for r in request.transactions]
    if not rows:
        return {"imported": 0, "duplicates": 0}

    days = [r.date for r in rows]
    held = Counter(
        (e["date"], e["side"], e["amount"])
        for e in _existing(db, account_id, min(days), max(days))
    )

    imported = duplicates = 0
    for row in rows:
        amount = row.amount.quantize(Decimal("0.01"))
        side = _side(row.direction)
        key = (row.date, side, amount)
        if not row.force and held[key] > 0:
            held[key] -= 1
            duplicates += 1
            continue

        description = row.description.strip()
        transaction = Transaction(
            ledger_id=current_ledger.id,
            created_by=current_user.id,
            transaction_date=row.date,
            description=description,
            status=TransactionStatus.DRAFT,
            source=TransactionSource.AI_IMPORT,
        )
        db.add(transaction)
        db.flush()
        db.add(JournalEntry(
            transaction_id=transaction.id,
            account_id=account_id,
            debit=amount if side == "debit" else Decimal("0.00"),
            credit=amount if side == "credit" else Decimal("0.00"),
            description=description,
        ))
        imported += 1

    db.add(ImportLog(
        ledger_id=current_ledger.id,
        user_id=current_user.id,
        bank_account_id=bank_account.id,
        file_name="AI-import",
        rows_imported=imported,
        rows_failed=0,
    ))
    db.commit()
    return {"imported": imported, "duplicates": duplicates}
