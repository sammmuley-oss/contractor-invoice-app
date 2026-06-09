"""Reconciliation API endpoints — matching actions, aging, ledger, export."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.database import get_db
from app.models.bank_transaction import BankTransaction
from app.models.invoice import Invoice, InvoiceStatus
from app.services.reconciliation_service import ReconciliationService
from app.schemas.bank_statement import ManualMatchRequest

router = APIRouter(prefix="/api/reconciliation", tags=["Reconciliation"])


# ─── Summary ──────────────────────────────────────────────

@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """Get reconciliation dashboard summary."""
    return ReconciliationService.get_summary(db)


# ─── Transactions ─────────────────────────────────────────

@router.get("/transactions")
def get_transactions(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get reconciliation transactions with optional status filter."""
    query = db.query(BankTransaction).filter(BankTransaction.credit_amount > 0)

    if status:
        query = query.filter(BankTransaction.match_status == status)

    total = query.count()

    transactions = (
        query
        .options(joinedload(BankTransaction.matched_invoice))
        .order_by(desc(BankTransaction.transaction_id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for t in transactions:
        company_name = None
        invoice_amount = None
        if t.matched_invoice and t.matched_invoice.company:
            company_name = t.matched_invoice.company.company_name
            invoice_amount = float(t.matched_invoice.net_receivable or 0)
        elif t.matched_invoice:
            invoice_amount = float(t.matched_invoice.net_receivable or 0)

        # Get bank name from statement
        bank_name = None
        if t.statement:
            bank_name = t.statement.bank_name

        items.append({
            "transaction_id": t.transaction_id,
            "statement_id": t.statement_id,
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
            "company_name": company_name,
            "invoice_amount": invoice_amount,
            "bank_name": bank_name,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ─── Actions ──────────────────────────────────────────────

@router.post("/approve/{transaction_id}")
def approve_match(transaction_id: int, db: Session = Depends(get_db)):
    """Approve a matched/needs-review transaction — creates payment."""
    try:
        return ReconciliationService.approve_match(db, transaction_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reject/{transaction_id}")
def reject_match(transaction_id: int, db: Session = Depends(get_db)):
    """Reject a match."""
    try:
        return ReconciliationService.reject_match(db, transaction_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/manual-match")
def manual_match(data: ManualMatchRequest, db: Session = Depends(get_db)):
    """Manually link a transaction to an invoice."""
    try:
        return ReconciliationService.manual_match(
            db, data.transaction_id, data.invoice_number,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Aging Report ─────────────────────────────────────────

@router.get("/aging")
def get_aging_report(db: Session = Depends(get_db)):
    """Get payment aging report."""
    return ReconciliationService.get_aging_report(db)


# ─── Company Ledger ───────────────────────────────────────

@router.get("/ledger/{gst_number}")
def get_company_ledger(gst_number: str, db: Session = Depends(get_db)):
    """Get company ledger with chronological entries."""
    try:
        return ReconciliationService.get_company_ledger(db, gst_number)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── Possible invoices for manual match ───────────────────

@router.get("/invoices")
def get_matchable_invoices(db: Session = Depends(get_db)):
    """Get unpaid/partially-paid invoices for manual matching."""
    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.company), joinedload(Invoice.payments))
        .filter(Invoice.invoice_status.in_([
            InvoiceStatus.UNPAID.value,
            InvoiceStatus.PARTIALLY_PAID.value,
        ]))
        .order_by(Invoice.invoice_date.desc())
        .all()
    )

    result = []
    for inv in invoices:
        total_paid = sum(float(p.amount_received or 0) for p in inv.payments)
        remaining = float(inv.net_receivable or 0) - total_paid
        result.append({
            "invoice_number": inv.invoice_number,
            "company_name": inv.company.company_name if inv.company else "",
            "total_amount": float(inv.total_amount or 0),
            "net_receivable": float(inv.net_receivable or 0),
            "total_paid": total_paid,
            "remaining": remaining,
            "invoice_status": inv.invoice_status,
        })

    return result


# ─── Export ───────────────────────────────────────────────

@router.get("/export/{report_type}")
def export_report(
    report_type: str,
    gst_number: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Export reports as CSV.

    report_type: 'reconciliation', 'aging', 'ledger', 'transactions'
    """
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "aging":
        data = ReconciliationService.get_aging_report(db)
        writer.writerow([
            "Invoice Number", "Company", "GST Number", "Invoice Date",
            "Due Date", "Net Receivable (₹)", "Total Paid (₹)",
            "Outstanding (₹)", "Days Pending", "Aging Bucket",
        ])
        for row in data:
            writer.writerow([
                row["invoice_number"], row["company_name"], row["gst_number"],
                row["invoice_date"], row["due_date"],
                f'{row["net_receivable"]:,.2f}', f'{row["total_paid"]:,.2f}',
                f'{row["outstanding"]:,.2f}', row["days_pending"], row["bucket"],
            ])

    elif report_type == "ledger" and gst_number:
        try:
            data = ReconciliationService.get_company_ledger(db, gst_number)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        writer.writerow([
            "Date", "Type", "Reference", "Description",
            "Invoice Amount (₹)", "TDS Deducted (₹)", "Retention (₹)",
            "Payment Received (₹)", "Running Balance (₹)",
        ])
        for entry in data["entries"]:
            writer.writerow([
                entry["date"], entry["type"], entry["reference"],
                entry["description"],
                f'{entry["invoice_amount"]:,.2f}' if entry["invoice_amount"] else "",
                f'{entry["tds_deducted"]:,.2f}' if entry["tds_deducted"] else "",
                f'{entry["retention_held"]:,.2f}' if entry["retention_held"] else "",
                f'{entry["payment_received"]:,.2f}' if entry["payment_received"] else "",
                f'{entry["running_balance"]:,.2f}',
            ])

    elif report_type == "reconciliation" or report_type == "transactions":
        txns = (
            db.query(BankTransaction)
            .filter(BankTransaction.credit_amount > 0)
            .order_by(BankTransaction.transaction_id)
            .all()
        )
        writer.writerow([
            "Transaction ID", "Date", "Description", "Credit Amount (₹)",
            "UTR Number", "Reference", "Sender", "Match Status",
            "Matched Invoice", "Confidence %",
        ])
        for t in txns:
            writer.writerow([
                t.transaction_id,
                t.transaction_date.isoformat() if t.transaction_date else "",
                t.description or "",
                f'{float(t.credit_amount):,.2f}',
                t.utr_number or "",
                t.reference_number or "",
                t.sender_name or "",
                t.match_status,
                t.matched_invoice_number or "",
                float(t.confidence_score) if t.confidence_score else "",
            ])
    else:
        raise HTTPException(status_code=400, detail="Invalid report type.")

    output.seek(0)
    filename = f"{report_type}_report.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
