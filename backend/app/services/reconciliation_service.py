"""Auto-reconciliation engine — matches bank transactions against invoices.

Confidence scoring:
    100% = Exact invoice number found in description
     95% = Company name + exact amount match
     95% = GST number in reference + amount match
     90% = UTR/reference + amount match
     80% = Amount + near due date (±7 days)
    <80% = Multiple possible matches → Needs Review
"""

import re
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.models.bank_transaction import BankTransaction
from app.models.bank_statement import BankStatement
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.company import Company
from app.services.payment_service import PaymentService
from app.schemas.payment import PaymentCreate


class ReconciliationService:
    """Smart matching engine for bank transactions → invoices."""

    @staticmethod
    def reconcile_statement(db: Session, statement_id: int) -> dict:
        """Run auto-reconciliation on all credit transactions in a statement.

        Returns summary: {matched, needs_review, unmatched}
        """
        transactions = (
            db.query(BankTransaction)
            .filter(
                BankTransaction.statement_id == statement_id,
                BankTransaction.credit_amount > 0,
                BankTransaction.match_status == "Unmatched",
            )
            .all()
        )

        counts = {"matched": 0, "needs_review": 0, "unmatched": 0}

        for txn in transactions:
            result = ReconciliationService._match_transaction(db, txn)
            if result["status"] == "Matched":
                counts["matched"] += 1
            elif result["status"] == "Needs_Review":
                counts["needs_review"] += 1
            else:
                counts["unmatched"] += 1

        db.commit()
        return counts

    @staticmethod
    def _match_transaction(db: Session, txn: BankTransaction) -> dict:
        """Try to match a single transaction using priority-ordered strategies."""
        credit = float(txn.credit_amount or 0)
        desc = (txn.description or "").upper()

        # Get all unpaid/partially paid invoices
        outstanding = (
            db.query(Invoice)
            .options(joinedload(Invoice.company), joinedload(Invoice.payments))
            .filter(Invoice.invoice_status.in_([
                InvoiceStatus.UNPAID.value,
                InvoiceStatus.PARTIALLY_PAID.value,
            ]))
            .all()
        )

        if not outstanding:
            return {"status": "Unmatched"}

        # Strategy 1: Exact invoice number in description (100%)
        match = ReconciliationService._match_by_invoice_number(desc, outstanding)
        if match:
            txn.matched_invoice_number = match.invoice_number
            txn.confidence_score = 100
            txn.match_status = "Matched"
            return {"status": "Matched"}

        # Strategy 2: Company name + exact amount (95%)
        match = ReconciliationService._match_by_company_amount(
            desc, credit, outstanding,
        )
        if match:
            txn.matched_invoice_number = match.invoice_number
            txn.confidence_score = 95
            txn.match_status = "Matched"
            return {"status": "Matched"}

        # Strategy 3: GST number in reference + amount (95%)
        ref_text = f"{txn.reference_number or ''} {desc}"
        match = ReconciliationService._match_by_gst_amount(
            ref_text, credit, outstanding,
        )
        if match:
            txn.matched_invoice_number = match.invoice_number
            txn.confidence_score = 95
            txn.match_status = "Matched"
            return {"status": "Matched"}

        # Strategy 4: UTR/reference + amount (90%)
        if txn.utr_number:
            match = ReconciliationService._match_by_utr_amount(
                credit, outstanding,
            )
            if match:
                txn.matched_invoice_number = match.invoice_number
                txn.confidence_score = 90
                txn.match_status = "Matched"
                return {"status": "Matched"}

        # Strategy 5: Amount + near due date (80%)
        matches = ReconciliationService._match_by_amount_date(
            credit, txn.transaction_date, outstanding, db,
        )
        if len(matches) == 1:
            txn.matched_invoice_number = matches[0].invoice_number
            txn.confidence_score = 80
            txn.match_status = "Needs_Review"
            return {"status": "Needs_Review"}
        elif len(matches) > 1:
            # Multiple possible matches — pick the best but flag for review
            txn.matched_invoice_number = matches[0].invoice_number
            txn.confidence_score = 70
            txn.match_status = "Needs_Review"
            return {"status": "Needs_Review"}

        return {"status": "Unmatched"}

    # ─── Matching Strategies ──────────────────────────────

    @staticmethod
    def _match_by_invoice_number(
        desc: str, invoices: list[Invoice],
    ) -> Optional[Invoice]:
        """Look for exact invoice number in description."""
        for inv in invoices:
            inv_num = inv.invoice_number.upper()
            if inv_num in desc:
                return inv
            # Also try without hyphens
            inv_num_clean = inv_num.replace('-', '')
            if inv_num_clean in desc.replace('-', '').replace(' ', ''):
                return inv
        return None

    @staticmethod
    def _match_by_company_amount(
        desc: str, amount: float, invoices: list[Invoice],
    ) -> Optional[Invoice]:
        """Match by company name in description + exact remaining amount."""
        for inv in invoices:
            if not inv.company:
                continue
            company_name = inv.company.company_name.upper()
            # Check if company name (or significant part) appears in description
            name_words = company_name.split()
            # Match if at least the first 2 significant words match
            significant_words = [w for w in name_words if len(w) > 2]
            matched_words = sum(1 for w in significant_words if w in desc)

            if matched_words >= min(2, len(significant_words)):
                remaining = ReconciliationService._get_remaining(inv)
                if abs(amount - remaining) < 1:  # tolerance ₹1
                    return inv
        return None

    @staticmethod
    def _match_by_gst_amount(
        ref_text: str, amount: float, invoices: list[Invoice],
    ) -> Optional[Invoice]:
        """Match by GST number in reference/description + amount."""
        ref_upper = ref_text.upper()
        for inv in invoices:
            gst = inv.gst_number.upper()
            if gst in ref_upper:
                remaining = ReconciliationService._get_remaining(inv)
                if abs(amount - remaining) < 1:
                    return inv
        return None

    @staticmethod
    def _match_by_utr_amount(
        amount: float, invoices: list[Invoice],
    ) -> Optional[Invoice]:
        """Match by amount when UTR is present (higher confidence)."""
        matches = []
        for inv in invoices:
            remaining = ReconciliationService._get_remaining(inv)
            if abs(amount - remaining) < 1:
                matches.append(inv)
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _match_by_amount_date(
        amount: float, txn_date, invoices: list[Invoice], db: Session,
    ) -> list[Invoice]:
        """Match by amount + transaction near due date (±7 days)."""
        matches = []
        for inv in invoices:
            remaining = ReconciliationService._get_remaining(inv)
            if abs(amount - remaining) < 1:
                # Check if transaction is within ±7 days of due date
                if txn_date and inv.due_date:
                    delta = abs((txn_date - inv.due_date).days)
                    if delta <= 7:
                        matches.append(inv)
                else:
                    # No date info — still a possible match but lower confidence
                    matches.append(inv)
        return matches

    @staticmethod
    def _get_remaining(inv: Invoice) -> float:
        """Get remaining balance on an invoice."""
        total_paid = sum(float(p.amount_received or 0) for p in inv.payments)
        return float(inv.net_receivable or 0) - total_paid

    # ─── User Actions ─────────────────────────────────────

    @staticmethod
    def approve_match(db: Session, transaction_id: int) -> dict:
        """Approve a matched/needs-review transaction — creates a Payment."""
        txn = db.query(BankTransaction).filter(
            BankTransaction.transaction_id == transaction_id
        ).first()
        if not txn:
            raise ValueError("Transaction not found.")
        if not txn.matched_invoice_number:
            raise ValueError("No invoice matched to this transaction.")
        if txn.match_status == "Matched" and txn.confidence_score == 100:
            # Already auto-matched — check if payment already created
            existing = (
                db.query(Payment)
                .filter(
                    Payment.invoice_number == txn.matched_invoice_number,
                    Payment.reference_number == f"BANK-TXN-{txn.transaction_id}",
                )
                .first()
            )
            if existing:
                return {"message": "Already processed", "payment_id": existing.payment_id}

        # Create payment via PaymentService
        payment_data = PaymentCreate(
            payment_date=txn.transaction_date or txn.created_date.date(),
            amount_received=float(txn.credit_amount),
            payment_mode="Bank Statement Import",
            reference_number=f"BANK-TXN-{txn.transaction_id}",
            remarks=f"Auto-matched from bank statement. "
                    f"UTR: {txn.utr_number or 'N/A'}. "
                    f"Confidence: {txn.confidence_score}%",
        )

        try:
            result = PaymentService.create(
                db, txn.matched_invoice_number, payment_data,
            )
            txn.match_status = "Matched"
            db.commit()
            return {
                "message": "Payment created and invoice updated",
                "payment_id": result.payment_id,
            }
        except ValueError as e:
            # Payment exceeds remaining — partial or already paid
            txn.match_status = "Rejected"
            txn.confidence_score = 0
            db.commit()
            raise ValueError(f"Could not create payment: {e}")

    @staticmethod
    def reject_match(db: Session, transaction_id: int) -> dict:
        """Reject a match — mark transaction as Rejected."""
        txn = db.query(BankTransaction).filter(
            BankTransaction.transaction_id == transaction_id
        ).first()
        if not txn:
            raise ValueError("Transaction not found.")
        txn.match_status = "Rejected"
        txn.matched_invoice_number = None
        txn.confidence_score = None
        db.commit()
        return {"message": "Match rejected"}

    @staticmethod
    def manual_match(
        db: Session, transaction_id: int, invoice_number: str,
    ) -> dict:
        """Manually link a transaction to an invoice and create payment."""
        txn = db.query(BankTransaction).filter(
            BankTransaction.transaction_id == transaction_id
        ).first()
        if not txn:
            raise ValueError("Transaction not found.")

        invoice = db.query(Invoice).filter(
            Invoice.invoice_number == invoice_number.upper()
        ).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_number} not found.")

        txn.matched_invoice_number = invoice.invoice_number
        txn.confidence_score = 100
        txn.match_status = "Matched"

        # Create payment
        payment_data = PaymentCreate(
            payment_date=txn.transaction_date or txn.created_date.date(),
            amount_received=float(txn.credit_amount),
            payment_mode="Bank Statement Import (Manual)",
            reference_number=f"BANK-TXN-{txn.transaction_id}",
            remarks=f"Manually matched from bank statement. "
                    f"UTR: {txn.utr_number or 'N/A'}",
        )

        result = PaymentService.create(db, invoice.invoice_number, payment_data)
        return {
            "message": "Manually matched and payment created",
            "payment_id": result.payment_id,
        }

    # ─── Reports ──────────────────────────────────────────

    @staticmethod
    def get_summary(db: Session) -> dict:
        """Get reconciliation summary counts."""
        total = db.query(func.count(BankTransaction.transaction_id)).filter(
            BankTransaction.credit_amount > 0
        ).scalar() or 0

        matched = db.query(func.count(BankTransaction.transaction_id)).filter(
            BankTransaction.match_status == "Matched",
            BankTransaction.credit_amount > 0,
        ).scalar() or 0

        needs_review = db.query(func.count(BankTransaction.transaction_id)).filter(
            BankTransaction.match_status == "Needs_Review",
            BankTransaction.credit_amount > 0,
        ).scalar() or 0

        unmatched = db.query(func.count(BankTransaction.transaction_id)).filter(
            BankTransaction.match_status == "Unmatched",
            BankTransaction.credit_amount > 0,
        ).scalar() or 0

        rejected = db.query(func.count(BankTransaction.transaction_id)).filter(
            BankTransaction.match_status == "Rejected",
            BankTransaction.credit_amount > 0,
        ).scalar() or 0

        matched_amt = db.query(func.sum(BankTransaction.credit_amount)).filter(
            BankTransaction.match_status == "Matched",
        ).scalar() or 0

        unmatched_amt = db.query(func.sum(BankTransaction.credit_amount)).filter(
            BankTransaction.match_status.in_(["Unmatched", "Needs_Review"]),
        ).scalar() or 0

        return {
            "total_transactions": total,
            "matched": matched,
            "needs_review": needs_review,
            "unmatched": unmatched,
            "rejected": rejected,
            "total_matched_amount": float(matched_amt),
            "total_unmatched_amount": float(unmatched_amt),
        }

    @staticmethod
    def get_aging_report(db: Session) -> list[dict]:
        """Generate payment aging report grouped by age buckets."""
        from datetime import date as date_type

        today = date_type.today()
        invoices = (
            db.query(Invoice)
            .options(joinedload(Invoice.company), joinedload(Invoice.payments))
            .filter(Invoice.invoice_status.in_([
                InvoiceStatus.UNPAID.value,
                InvoiceStatus.PARTIALLY_PAID.value,
            ]))
            .all()
        )

        report = []
        for inv in invoices:
            total_paid = sum(float(p.amount_received or 0) for p in inv.payments)
            outstanding = float(inv.net_receivable or 0) - total_paid
            if outstanding <= 0:
                continue

            days_pending = (today - inv.due_date).days if inv.due_date else 0

            if days_pending <= 30:
                bucket = "0-30 Days"
            elif days_pending <= 60:
                bucket = "31-60 Days"
            elif days_pending <= 90:
                bucket = "61-90 Days"
            elif days_pending <= 180:
                bucket = "91-180 Days"
            else:
                bucket = "180+ Days"

            report.append({
                "invoice_number": inv.invoice_number,
                "company_name": inv.company.company_name if inv.company else "",
                "gst_number": inv.gst_number,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "total_amount": float(inv.total_amount or 0),
                "net_receivable": float(inv.net_receivable or 0),
                "total_paid": total_paid,
                "outstanding": outstanding,
                "days_pending": days_pending,
                "bucket": bucket,
                "is_overdue": days_pending > 0,
            })

        return sorted(report, key=lambda x: x["days_pending"], reverse=True)

    @staticmethod
    def get_company_ledger(db: Session, gst_number: str) -> dict:
        """Generate company ledger with chronological transactions."""
        company = db.query(Company).filter(
            Company.gst_number == gst_number.upper()
        ).first()
        if not company:
            raise ValueError(f"Company with GST {gst_number} not found.")

        invoices = (
            db.query(Invoice)
            .options(joinedload(Invoice.payments))
            .filter(Invoice.gst_number == gst_number.upper())
            .order_by(Invoice.invoice_date)
            .all()
        )

        entries = []
        running_balance = 0

        for inv in invoices:
            # Invoice raised entry
            net_rec = float(inv.net_receivable or 0)
            running_balance += net_rec
            entries.append({
                "date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "type": "Invoice",
                "reference": inv.invoice_number,
                "description": inv.work_description or "Invoice raised",
                "invoice_amount": float(inv.total_amount or 0),
                "tds_deducted": float(inv.tds_amount or 0),
                "retention_held": float(inv.retention_amount or 0),
                "payment_received": 0,
                "running_balance": running_balance,
            })

            # Payment entries for this invoice
            for p in sorted(inv.payments, key=lambda x: x.payment_date or x.created_date):
                amt = float(p.amount_received or 0)
                running_balance -= amt
                entries.append({
                    "date": p.payment_date.isoformat() if p.payment_date else None,
                    "type": "Payment",
                    "reference": p.reference_number or f"PMT-{p.payment_id}",
                    "description": f"{p.payment_mode} - {p.remarks or ''}".strip(' -'),
                    "invoice_amount": 0,
                    "tds_deducted": 0,
                    "retention_held": 0,
                    "payment_received": amt,
                    "running_balance": running_balance,
                })

        total_invoiced = sum(float(i.total_amount or 0) for i in invoices)
        total_tds = sum(float(i.tds_amount or 0) for i in invoices)
        total_retention = sum(float(i.retention_amount or 0) for i in invoices)
        total_net = sum(float(i.net_receivable or 0) for i in invoices)
        total_paid = sum(
            float(p.amount_received or 0)
            for i in invoices for p in i.payments
        )

        return {
            "company": {
                "gst_number": company.gst_number,
                "company_name": company.company_name,
                "contact_person": company.contact_person,
                "mobile": company.mobile,
                "email": company.email,
            },
            "summary": {
                "total_invoiced": total_invoiced,
                "total_tds": total_tds,
                "total_retention": total_retention,
                "total_net_receivable": total_net,
                "total_paid": total_paid,
                "outstanding": total_net - total_paid,
            },
            "entries": entries,
        }
