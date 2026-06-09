"""Payment service - business logic for recording and tracking payments."""

from typing import Optional
from sqlalchemy.orm import Session, joinedload

from app.models.payment import Payment
from app.models.invoice import Invoice
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.invoice_service import InvoiceService
from app.utils.indian_currency import round_decimal


class PaymentService:
    """Service layer for payment operations."""

    @staticmethod
    def get_all(
        db: Session,
        invoice_number: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[PaymentResponse]:
        """Get all payments with optional filters."""
        query = db.query(Payment).options(joinedload(Payment.invoice).joinedload(Invoice.company))

        if invoice_number:
            query = query.filter(Payment.invoice_number == invoice_number.upper())

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Payment.invoice_number.ilike(search_term)) |
                (Payment.reference_number.ilike(search_term)) |
                (Payment.remarks.ilike(search_term))
            )

        payments = query.order_by(Payment.payment_date.desc()).all()

        result = []
        for payment in payments:
            company_name = ""
            gst_number = ""
            net_receivable = 0
            invoice_status = ""

            if payment.invoice:
                gst_number = payment.invoice.gst_number
                net_receivable = float(payment.invoice.net_receivable or 0)
                invoice_status = payment.invoice.invoice_status
                if payment.invoice.company:
                    company_name = payment.invoice.company.company_name

            result.append(PaymentResponse(
                payment_id=payment.payment_id,
                invoice_number=payment.invoice_number,
                payment_date=payment.payment_date,
                amount_received=float(payment.amount_received),
                payment_mode=payment.payment_mode,
                reference_number=payment.reference_number,
                remarks=payment.remarks,
                created_date=payment.created_date,
                company_name=company_name,
                gst_number=gst_number,
                net_receivable=net_receivable,
                invoice_status=invoice_status,
            ))

        return result

    @staticmethod
    def create(db: Session, invoice_number: str, data: PaymentCreate) -> PaymentResponse:
        """Record a new payment against an invoice."""
        # Verify invoice exists
        invoice = (
            db.query(Invoice)
            .options(joinedload(Invoice.payments), joinedload(Invoice.company))
            .filter(Invoice.invoice_number == invoice_number.upper())
            .first()
        )
        if not invoice:
            raise ValueError(f"Invoice {invoice_number} not found.")

        # Check if payment would exceed net receivable
        current_paid = sum(float(p.amount_received or 0) for p in invoice.payments)
        net_receivable = float(invoice.net_receivable or 0)
        remaining = round_decimal(net_receivable - current_paid)

        if data.amount_received > remaining and remaining > 0:
            raise ValueError(
                f"Payment amount (₹{data.amount_received:,.2f}) exceeds "
                f"remaining balance (₹{remaining:,.2f})."
            )

        payment = Payment(
            invoice_number=invoice_number.upper(),
            payment_date=data.payment_date,
            amount_received=data.amount_received,
            payment_mode=data.payment_mode,
            reference_number=data.reference_number,
            remarks=data.remarks,
        )

        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Update invoice status
        InvoiceService.update_invoice_status(db, invoice)

        company_name = invoice.company.company_name if invoice.company else ""

        return PaymentResponse(
            payment_id=payment.payment_id,
            invoice_number=payment.invoice_number,
            payment_date=payment.payment_date,
            amount_received=float(payment.amount_received),
            payment_mode=payment.payment_mode,
            reference_number=payment.reference_number,
            remarks=payment.remarks,
            created_date=payment.created_date,
            company_name=company_name,
            gst_number=invoice.gst_number,
            net_receivable=float(invoice.net_receivable),
            invoice_status=invoice.invoice_status,
        )

    @staticmethod
    def delete(db: Session, payment_id: int) -> bool:
        """Delete a payment and update invoice status."""
        payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
        if not payment:
            return False

        invoice_number = payment.invoice_number
        db.delete(payment)
        db.commit()

        # Update invoice status
        invoice = (
            db.query(Invoice)
            .options(joinedload(Invoice.payments))
            .filter(Invoice.invoice_number == invoice_number)
            .first()
        )
        if invoice:
            InvoiceService.update_invoice_status(db, invoice)

        return True
