from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
import csv
import io
import json

from backend.database import get_db
from ..models import Transaction, JournalEntry, User, Ledger, BankAccount, Account, TransactionCategory, Receipt, ImportLog, CSVMapping, TransactionStatus
from ..schemas import Transaction as TransactionSchema, TransactionCreate, PaginatedTransactions, ChainSuggestionsResponse, ChainTransactionsRequest
from ..auth import get_current_active_user, get_current_ledger
from ..transaction_chaining import TransactionChainMatcher

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/", response_model=List[TransactionSchema])
def get_transactions(
    skip: int = 0,
    limit: int = 100,
    start_date: date = None,
    end_date: date = None,
    account_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    query = db.query(Transaction).options(
        joinedload(Transaction.journal_entries).joinedload(JournalEntry.account)
    ).filter(Transaction.ledger_id == current_ledger.id)

    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    if account_id:
        query = query.filter(
            Transaction.journal_entries.any(JournalEntry.account_id == account_id)
        )

    transactions = query.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()
    return transactions


@router.post("/", response_model=TransactionSchema)
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    total_debit = sum(entry.debit for entry in transaction.journal_entries)
    total_credit = sum(entry.credit for entry in transaction.journal_entries)

    if abs(total_debit - total_credit) > Decimal("0.01"):
        raise HTTPException(
            status_code=400,
            detail=f"Transaction not balanced. Debit: {total_debit}, Credit: {total_credit}"
        )

    db_transaction = Transaction(
        ledger_id=current_ledger.id,
        created_by=current_user.id,
        transaction_date=transaction.transaction_date,
        description=transaction.description,
        reference=transaction.reference
    )
    db.add(db_transaction)
    db.flush()

    for entry in transaction.journal_entries:
        db_entry = JournalEntry(
            transaction_id=db_transaction.id,
            account_id=entry.account_id,
            debit=entry.debit,
            credit=entry.credit,
            description=entry.description
        )
        db.add(db_entry)

    for category_id in transaction.category_ids:
        db_cat = TransactionCategory(
            transaction_id=db_transaction.id,
            category_id=category_id
        )
        db.add(db_cat)

    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@router.get("/queue", response_model=PaginatedTransactions)
def get_posting_queue(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Get all DRAFT transactions (posting queue) with pagination"""
    # Get total count
    total = db.query(Transaction).filter(
        Transaction.ledger_id == current_ledger.id,
        Transaction.status == TransactionStatus.DRAFT
    ).count()

    # Get paginated transactions
    transactions = db.query(Transaction).options(
        joinedload(Transaction.journal_entries).joinedload(JournalEntry.account)
    ).filter(
        Transaction.ledger_id == current_ledger.id,
        Transaction.status == TransactionStatus.DRAFT
    ).order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()

    return {
        "transactions": transactions,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/chain-suggestions", response_model=ChainSuggestionsResponse)
def get_chain_suggestions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Find pairs of DRAFT bank-synced transactions that can be chained together."""
    suggestions = TransactionChainMatcher.find_chain_candidates(db, current_ledger.id)
    return {
        "suggestions": [
            {
                "primary_transaction_id": s.primary_transaction_id,
                "secondary_transaction_id": s.secondary_transaction_id,
                "primary_description": s.primary_description,
                "secondary_description": s.secondary_description,
                "primary_account_name": s.primary_account_name,
                "secondary_account_name": s.secondary_account_name,
                "amount": s.amount,
                "primary_date": s.primary_date,
                "secondary_date": s.secondary_date,
                "confidence": s.confidence
            }
            for s in suggestions
        ],
        "total": len(suggestions)
    }


@router.post("/chain")
def chain_transactions(
    request: ChainTransactionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Merge two DRAFT transactions into one balanced transaction."""
    try:
        merged = TransactionChainMatcher.chain_transactions(
            db=db,
            ledger_id=current_ledger.id,
            primary_id=request.primary_transaction_id,
            secondary_id=request.secondary_transaction_id,
            auto_post=request.auto_post
        )
        return {
            "message": "Transaksjoner kjedet sammen",
            "transaction_id": merged.id,
            "status": merged.status.value if hasattr(merged.status, 'value') else str(merged.status),
            "journal_entries": len(merged.journal_entries)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{transaction_id}", response_model=TransactionSchema)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.ledger_id == current_ledger.id
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.put("/{transaction_id}", response_model=TransactionSchema)
def update_transaction(
    transaction_id: int,
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    db_transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.ledger_id == current_ledger.id
    ).first()
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Validate balance
    total_debit = sum(entry.debit for entry in transaction.journal_entries)
    total_credit = sum(entry.credit for entry in transaction.journal_entries)

    if abs(total_debit - total_credit) > Decimal("0.01"):
        raise HTTPException(
            status_code=400,
            detail=f"Transaction not balanced. Debit: {total_debit}, Credit: {total_credit}"
        )

    # Update transaction fields
    db_transaction.transaction_date = transaction.transaction_date
    db_transaction.description = transaction.description
    db_transaction.reference = transaction.reference

    # Delete existing journal entries
    db.query(JournalEntry).filter(JournalEntry.transaction_id == transaction_id).delete()

    # Create new journal entries
    for entry in transaction.journal_entries:
        db_entry = JournalEntry(
            transaction_id=db_transaction.id,
            account_id=entry.account_id,
            debit=entry.debit,
            credit=entry.credit,
            description=entry.description
        )
        db.add(db_entry)

    # Delete existing categories
    db.query(TransactionCategory).filter(TransactionCategory.transaction_id == transaction_id).delete()

    # Add new categories
    for category_id in transaction.category_ids:
        db_cat = TransactionCategory(
            transaction_id=db_transaction.id,
            category_id=category_id
        )
        db.add(db_cat)

    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.ledger_id == current_ledger.id
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    db.delete(transaction)
    db.commit()
    return {"message": "Transaction deleted"}


@router.post("/csv-preview")
async def csv_preview(
    file: UploadFile = File(...),
    delimiter: str = Form(","),
    current_user: User = Depends(get_current_active_user)
):
    """Preview CSV file contents and return column names and first 5 rows"""
    try:
        contents = await file.read()
        decoded = contents.decode('utf-8')

        # Read CSV with specified delimiter
        csv_file = io.StringIO(decoded)
        reader = csv.reader(csv_file, delimiter=delimiter)

        # Get all rows
        all_rows = list(reader)

        if len(all_rows) == 0:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        # First row is assumed to be headers
        headers = all_rows[0]
        data_rows = all_rows[1:6]  # Get first 5 data rows

        return {
            "columns": headers,
            "preview": data_rows,
            "total_rows": len(all_rows) - 1
        }
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding error. Please use UTF-8 encoded CSV")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading CSV: {str(e)}")


@router.post("/import-csv/{bank_account_id}")
async def import_csv(
    bank_account_id: int,
    file: UploadFile = File(...),
    mapping_config: str = Form(...),
    csv_mapping_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Import CSV with custom column mapping"""
    bank_account = db.query(BankAccount).filter(
        BankAccount.id == bank_account_id,
        BankAccount.ledger_id == current_ledger.id
    ).first()
    if not bank_account:
        raise HTTPException(status_code=404, detail="Bank account not found")

    # Get the linked account to check if it's ASSET or LIABILITY
    account = db.query(Account).filter(Account.id == bank_account.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Linked account not found")

    is_liability = account.account_type == "LIABILITY"

    # Parse mapping config
    try:
        config = json.loads(mapping_config)
        date_col = config['date_column']
        desc_col = config['description_column']
        amount_col = config['amount_column']
        ref_col = config.get('reference_column')
        skip_rows = config.get('skip_rows', 0)
        date_fmt = config.get('date_format', 'YYYY-MM-DD')
        decimal_sep = config.get('decimal_separator', '.')
        delimiter = config.get('delimiter', ',')
        invert_amount = config.get('invert_amount', False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid mapping config: {str(e)}")

    contents = await file.read()
    decoded = contents.decode('utf-8')

    # Read all rows
    csv_file = io.StringIO(decoded)
    reader = csv.DictReader(csv_file, delimiter=delimiter)

    imported = 0
    failed = 0
    errors = []

    for idx, row in enumerate(reader):
        if idx < skip_rows:
            continue

        try:
            # Parse date
            date_str = row.get(date_col, '').strip()
            if not date_str:
                raise ValueError("Missing date")

            # Handle different date formats
            if date_fmt == 'DD.MM.YYYY':
                trans_date = datetime.strptime(date_str, '%d.%m.%Y').date()
            elif date_fmt == 'DD/MM/YYYY':
                trans_date = datetime.strptime(date_str, '%d/%m/%Y').date()
            elif date_fmt == 'MM/DD/YYYY':
                trans_date = datetime.strptime(date_str, '%m/%d/%Y').date()
            else:  # YYYY-MM-DD
                trans_date = date.fromisoformat(date_str)

            # Parse description
            description = row.get(desc_col, '').strip()
            if not description:
                description = "Imported transaction"

            # Parse amount
            amount_str = row.get(amount_col, '0').strip()
            if decimal_sep == ',':
                amount_str = amount_str.replace('.', '').replace(',', '.')
            amount = Decimal(amount_str)

            # Invert amount if configured (for banks where negative = expense)
            if invert_amount:
                amount = -amount

            if amount == 0:
                failed += 1
                errors.append(f"Row {idx + 1}: Zero amount")
                continue

            # Parse reference
            reference = row.get(ref_col, '').strip() if ref_col else ''

            # Create transaction with DRAFT status for review
            db_transaction = Transaction(
                ledger_id=current_ledger.id,
                created_by=current_user.id,
                transaction_date=trans_date,
                description=description,
                reference=reference,
                status=TransactionStatus.DRAFT
            )
            db.add(db_transaction)
            db.flush()

            # Create journal entries
            # For ASSET accounts (bank accounts): positive = debit, negative = credit
            # For LIABILITY accounts (credit cards): positive = credit, negative = debit
            if is_liability:
                # Credit card: positive amount = expense (increases liability)
                if amount > 0:
                    db.add(JournalEntry(
                        transaction_id=db_transaction.id,
                        account_id=bank_account.account_id,
                        debit=Decimal("0.00"),
                        credit=amount
                    ))
                else:
                    # Negative amount = refund (decreases liability)
                    db.add(JournalEntry(
                        transaction_id=db_transaction.id,
                        account_id=bank_account.account_id,
                        debit=abs(amount),
                        credit=Decimal("0.00")
                    ))
            else:
                # Bank account: positive amount = deposit (increases asset)
                if amount > 0:
                    db.add(JournalEntry(
                        transaction_id=db_transaction.id,
                        account_id=bank_account.account_id,
                        debit=amount,
                        credit=Decimal("0.00")
                    ))
                else:
                    # Negative amount = withdrawal (decreases asset)
                    db.add(JournalEntry(
                        transaction_id=db_transaction.id,
                        account_id=bank_account.account_id,
                        debit=Decimal("0.00"),
                        credit=abs(amount)
                    ))

            imported += 1

        except Exception as e:
            failed += 1
            errors.append(f"Row {idx + 1}: {str(e)}")
            continue

    # Create import log
    import_log = ImportLog(
        ledger_id=current_ledger.id,
        user_id=current_user.id,
        bank_account_id=bank_account_id,
        csv_mapping_id=csv_mapping_id,
        file_name=file.filename,
        rows_imported=imported,
        rows_failed=failed
    )
    db.add(import_log)
    db.commit()

    return {
        "message": "Import completed",
        "imported": imported,
        "failed": failed,
        "errors": errors[:10]  # Return first 10 errors
    }


@router.post("/{transaction_id}/post")
def post_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Change transaction status from DRAFT to POSTED"""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.ledger_id == current_ledger.id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.status != TransactionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Transaction is not in DRAFT status")

    # Validate that transaction is balanced
    total_debit = sum(entry.debit for entry in transaction.journal_entries)
    total_credit = sum(entry.credit for entry in transaction.journal_entries)

    if abs(total_debit - total_credit) > Decimal("0.01"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot post unbalanced transaction. Debit: {total_debit}, Credit: {total_credit}"
        )

    # Validate that transaction has at least 2 entries
    if len(transaction.journal_entries) < 2:
        raise HTTPException(
            status_code=400,
            detail="Transaction must have at least 2 journal entries"
        )

    transaction.status = TransactionStatus.POSTED
    db.commit()

    return {"message": "Transaction posted successfully", "status": "POSTED"}


@router.post("/{transaction_id}/reconcile")
def reconcile_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Change transaction status to RECONCILED"""
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.ledger_id == current_ledger.id
    ).first()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.status == TransactionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Cannot reconcile DRAFT transaction. Post it first.")

    transaction.status = TransactionStatus.RECONCILED
    transaction.is_reconciled = True
    db.commit()

    return {"message": "Transaction reconciled successfully", "status": "RECONCILED"}


@router.post("/queue/post-all")
def post_all_draft_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Post all DRAFT transactions in the queue"""
    result = db.query(Transaction).filter(
        Transaction.ledger_id == current_ledger.id,
        Transaction.status == TransactionStatus.DRAFT
    ).update({"status": TransactionStatus.POSTED})

    db.commit()

    return {"message": f"Posted {result} transactions", "count": result}


@router.post("/{transaction_id}/reverse")
def reverse_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    """Create a reversing entry for a posted transaction (god regnskapsskikk)"""
    original = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.ledger_id == current_ledger.id
    ).first()

    if not original:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if original.status == TransactionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Cannot reverse DRAFT transaction. Delete it instead.")

    # Create reversing transaction
    reverse_transaction = Transaction(
        ledger_id=current_ledger.id,
        created_by=current_user.id,
        transaction_date=date.today(),
        description=f"REVERSERING: {original.description}",
        reference=f"REV-{original.id}",
        status=TransactionStatus.POSTED
    )
    db.add(reverse_transaction)
    db.flush()

    # Create reversed journal entries (swap debit/credit)
    for entry in original.journal_entries:
        reversed_entry = JournalEntry(
            transaction_id=reverse_transaction.id,
            account_id=entry.account_id,
            debit=entry.credit,  # Swap
            credit=entry.debit,  # Swap
            description=f"Reversering av postering {entry.id}"
        )
        db.add(reversed_entry)

    db.commit()
    db.refresh(reverse_transaction)

    return {
        "message": "Transaction reversed successfully",
        "original_id": transaction_id,
        "reversing_id": reverse_transaction.id
    }
