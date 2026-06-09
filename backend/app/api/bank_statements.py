"""Bank Statement upload and management API endpoints."""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.bank_statement import BankStatement
from app.models.bank_transaction import BankTransaction
from app.services.statement_parser import StatementParser
from app.services.reconciliation_service import ReconciliationService

router = APIRouter(prefix="/api/bank-statements", tags=["Bank Statements"])

SUPPORTED_EXTENSIONS = {"pdf", "csv", "xlsx", "xls"}
SUPPORTED_BANKS = [
    "SBI", "HDFC", "ICICI", "Axis", "Kotak",
    "BOB", "Canara", "Union", "PNB", "IndusInd", "Other",
]


@router.get("/banks")
def list_supported_banks():
    """Get list of supported banks."""
    return SUPPORTED_BANKS


@router.post("/upload")
async def upload_statement(
    file: UploadFile = File(...),
    bank_name: str = Form(...),
    db: Session = Depends(get_db),
):
    """Upload and parse a bank statement file."""
    # Validate file extension
    filename = file.filename or "unknown"
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '.{ext}'. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    # Read file
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    # Parse transactions
    try:
        transactions = StatementParser.parse(file_bytes, filename, bank_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse statement: {str(e)}",
        )

    if not transactions:
        raise HTTPException(
            status_code=400,
            detail="No transactions found in the uploaded file. "
                   "Please check the file format and ensure it contains transaction data.",
        )

    # Determine date range
    dates = [t["transaction_date"] for t in transactions if t.get("transaction_date")]
    start_date = min(dates) if dates else None
    end_date = max(dates) if dates else None

    # Create BankStatement record
    statement = BankStatement(
        bank_name=bank_name,
        file_name=filename,
        upload_date=datetime.utcnow(),
        statement_start_date=start_date,
        statement_end_date=end_date,
        total_transactions=len(transactions),
    )
    db.add(statement)
    db.flush()  # Get statement_id

    # Create BankTransaction records
    for txn in transactions:
        db_txn = BankTransaction(
            statement_id=statement.statement_id,
            transaction_date=txn.get("transaction_date"),
            description=txn.get("description"),
            credit_amount=txn.get("credit_amount", 0),
            debit_amount=txn.get("debit_amount", 0),
            utr_number=txn.get("utr_number"),
            reference_number=txn.get("reference_number"),
            sender_name=txn.get("sender_name"),
            match_status="Unmatched",
        )
        db.add(db_txn)

    db.commit()

    # Run auto-reconciliation
    recon_result = ReconciliationService.reconcile_statement(db, statement.statement_id)

    return {
        "message": "Statement uploaded and processed successfully",
        "statement_id": statement.statement_id,
        "total_transactions": len(transactions),
        "credits": sum(1 for t in transactions if t.get("credit_amount", 0) > 0),
        "debits": sum(1 for t in transactions if t.get("debit_amount", 0) > 0),
        "reconciliation": recon_result,
    }


@router.get("")
def list_statements(db: Session = Depends(get_db)):
    """Get all uploaded bank statements."""
    statements = (
        db.query(BankStatement)
        .order_by(BankStatement.upload_date.desc())
        .all()
    )
    return [
        {
            "statement_id": s.statement_id,
            "bank_name": s.bank_name,
            "file_name": s.file_name,
            "upload_date": s.upload_date.isoformat() if s.upload_date else None,
            "statement_start_date": s.statement_start_date.isoformat() if s.statement_start_date else None,
            "statement_end_date": s.statement_end_date.isoformat() if s.statement_end_date else None,
            "total_transactions": s.total_transactions,
        }
        for s in statements
    ]


@router.get("/{statement_id}")
def get_statement(statement_id: int, db: Session = Depends(get_db)):
    """Get statement details with all transactions."""
    statement = (
        db.query(BankStatement)
        .options(joinedload(BankStatement.transactions))
        .filter(BankStatement.statement_id == statement_id)
        .first()
    )
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found.")

    return {
        "statement": {
            "statement_id": statement.statement_id,
            "bank_name": statement.bank_name,
            "file_name": statement.file_name,
            "upload_date": statement.upload_date.isoformat() if statement.upload_date else None,
            "statement_start_date": statement.statement_start_date.isoformat() if statement.statement_start_date else None,
            "statement_end_date": statement.statement_end_date.isoformat() if statement.statement_end_date else None,
            "total_transactions": statement.total_transactions,
        },
        "transactions": [
            {
                "transaction_id": t.transaction_id,
                "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
                "description": t.description,
                "credit_amount": float(t.credit_amount or 0),
                "debit_amount": float(t.debit_amount or 0),
                "utr_number": t.utr_number,
                "reference_number": t.reference_number,
                "sender_name": t.sender_name,
                "match_status": t.match_status,
                "matched_invoice_number": t.matched_invoice_number,
                "confidence_score": float(t.confidence_score) if t.confidence_score else None,
            }
            for t in sorted(statement.transactions, key=lambda x: x.transaction_id)
        ],
    }


@router.delete("/{statement_id}")
def delete_statement(statement_id: int, db: Session = Depends(get_db)):
    """Delete a statement and all its transactions."""
    statement = db.query(BankStatement).filter(
        BankStatement.statement_id == statement_id
    ).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found.")
    db.delete(statement)
    db.commit()
    return {"message": "Statement deleted"}
