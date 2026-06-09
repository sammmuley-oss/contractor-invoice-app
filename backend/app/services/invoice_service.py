"""Invoice service - business logic with calculation engine."""

from typing import Optional
from datetime import date
import math

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.models.invoice import Invoice, InvoiceStatus
from app.models.company import Company
from app.models.payment import Payment
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceListResponse
from app.utils.indian_currency import round_decimal


class InvoiceService:
    """Service layer for invoice operations with calculation engine."""

    # ─── Calculation Engine ───────────────────────────────────

    @staticmethod
    def calculate_amounts(
        invoice_amount: float,
        gst_percentage: float,
        tds_percentage: float = 0,
        retention_percentage: float = 0,
    ) -> dict:
        """Calculate all derived financial amounts.

        Formula:
            GST Amount       = Invoice Amount × (GST% / 100)
            Total Amount     = Invoice Amount + GST Amount
            TDS Amount       = Total Amount × (TDS% / 100)
            Retention Amount = Total Amount × (Retention% / 100)
            Net Receivable   = Total Amount - TDS Amount - Retention Amount
        """
        gst_amount = round_decimal(invoice_amount * (gst_percentage / 100))
        total_amount = round_decimal(invoice_amount + gst_amount)
        tds_amount = round_decimal(total_amount * (tds_percentage / 100))
        retention_amount = round_decimal(total_amount * (retention_percentage / 100))
        net_receivable = round_decimal(total_amount - tds_amount - retention_amount)

        return {
            "gst_amount": gst_amount,
            "total_amount": total_amount,
            "tds_amount": tds_amount,
            "retention_amount": retention_amount,
            "net_receivable": net_receivable,
        }

    @staticmethod
    def get_total_paid(invoice: Invoice) -> float:
        """Sum of all payments for an invoice."""
        return sum(float(p.amount_received or 0) for p in invoice.payments)

    @staticmethod
    def derive_status(net_receivable: float, total_paid: float) -> str:
        """Derive invoice status based on payments.

        Rules:
            payment == 0                → Unpaid
            payment < net_receivable    → Partially Paid
            payment >= net_receivable   → Paid
        """
        if total_paid <= 0:
            return InvoiceStatus.UNPAID.value
        elif total_paid < net_receivable:
            return InvoiceStatus.PARTIALLY_PAID.value
        else:
            return InvoiceStatus.PAID.value

    @classmethod
    def update_invoice_status(cls, db: Session, invoice: Invoice):
        """Recalculate and update invoice status based on payments."""
        total_paid = cls.get_total_paid(invoice)
        net_receivable = float(invoice.net_receivable or 0)
        invoice.invoice_status = cls.derive_status(net_receivable, total_paid)
        db.commit()

    # ─── Invoice to Response ─────────────────────────────────

    @classmethod
    def to_response(cls, invoice: Invoice) -> InvoiceResponse:
        """Convert invoice model to response schema."""
        total_paid = cls.get_total_paid(invoice)
        net_receivable = float(invoice.net_receivable or 0)
        pending_amount = round_decimal(net_receivable - total_paid)
        if pending_amount < 0:
            pending_amount = 0

        company_name = invoice.company.company_name if invoice.company else ""

        return InvoiceResponse(
            invoice_number=invoice.invoice_number,
            gst_number=invoice.gst_number,
            company_name=company_name,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            work_description=invoice.work_description,
            site_location=invoice.site_location,
            invoice_amount=float(invoice.invoice_amount or 0),
            gst_percentage=float(invoice.gst_percentage or 0),
            gst_amount=float(invoice.gst_amount or 0),
            total_amount=float(invoice.total_amount or 0),
            tds_percentage=float(invoice.tds_percentage or 0),
            tds_amount=float(invoice.tds_amount or 0),
            retention_percentage=float(invoice.retention_percentage or 0),
            retention_amount=float(invoice.retention_amount or 0),
            net_receivable=net_receivable,
            total_paid=total_paid,
            pending_amount=pending_amount,
            invoice_status=invoice.invoice_status,
            created_date=invoice.created_date,
            updated_date=invoice.updated_date,
            payments=[
                {
                    "payment_id": p.payment_id,
                    "payment_date": p.payment_date,
                    "amount_received": float(p.amount_received),
                    "payment_mode": p.payment_mode,
                    "reference_number": p.reference_number,
                    "remarks": p.remarks,
                }
                for p in invoice.payments
            ],
            documents=[
                {
                    "document_id": d.document_id,
                    "document_name": d.document_name,
                    "file_type": d.file_type,
                    "file_size": d.file_size,
                    "upload_date": d.upload_date,
                }
                for d in invoice.documents
            ],
        )

    # ─── CRUD Operations ─────────────────────────────────────

    @classmethod
    def get_all(
        cls,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        gst_number: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        month: Optional[int] = None,
        year: Optional[int] = None,
        sort_by: str = "invoice_date",
        sort_order: str = "desc",
    ) -> InvoiceListResponse:
        """Get paginated invoices with filters."""
        query = db.query(Invoice).options(
            joinedload(Invoice.company),
            joinedload(Invoice.payments),
            joinedload(Invoice.documents),
        )

        # Filters
        if gst_number:
            query = query.filter(Invoice.gst_number == gst_number.upper())
        if status:
            query = query.filter(Invoice.invoice_status == status)
        if month:
            query = query.filter(
                db.query(Invoice).column_descriptions[0]["expr"].invoice_date if False else
                Invoice.invoice_date != None  # placeholder for month filter
            )
            # SQLite-compatible month filtering
            from sqlalchemy import extract
            query = query.filter(extract("month", Invoice.invoice_date) == month)
        if year:
            from sqlalchemy import extract
            query = query.filter(extract("year", Invoice.invoice_date) == year)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Invoice.invoice_number.ilike(search_term)) |
                (Invoice.work_description.ilike(search_term)) |
                (Invoice.site_location.ilike(search_term))
            )

        # Count total before pagination
        # Use a subquery approach to avoid issues with joinedload + count
        from sqlalchemy import func
        count_query = db.query(func.count(Invoice.invoice_number))
        if gst_number:
            count_query = count_query.filter(Invoice.gst_number == gst_number.upper())
        if status:
            count_query = count_query.filter(Invoice.invoice_status == status)
        if search:
            search_term = f"%{search}%"
            count_query = count_query.filter(
                (Invoice.invoice_number.ilike(search_term)) |
                (Invoice.work_description.ilike(search_term)) |
                (Invoice.site_location.ilike(search_term))
            )
        if month:
            from sqlalchemy import extract
            count_query = count_query.filter(extract("month", Invoice.invoice_date) == month)
        if year:
            from sqlalchemy import extract
            count_query = count_query.filter(extract("year", Invoice.invoice_date) == year)

        total = count_query.scalar()

        # Sorting
        sort_column = getattr(Invoice, sort_by, Invoice.invoice_date)
        if sort_order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Pagination
        offset = (page - 1) * page_size
        invoices = query.offset(offset).limit(page_size).all()

        # Deduplicate (joinedload can cause duplicates)
        seen = set()
        unique_invoices = []
        for inv in invoices:
            if inv.invoice_number not in seen:
                seen.add(inv.invoice_number)
                unique_invoices.append(inv)

        return InvoiceListResponse(
            items=[cls.to_response(inv) for inv in unique_invoices],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total > 0 else 1,
        )

    @classmethod
    def get_by_number(cls, db: Session, invoice_number: str) -> Optional[InvoiceResponse]:
        """Get a single invoice by number."""
        invoice = (
            db.query(Invoice)
            .options(
                joinedload(Invoice.company),
                joinedload(Invoice.payments),
                joinedload(Invoice.documents),
            )
            .filter(Invoice.invoice_number == invoice_number.upper())
            .first()
        )
        if not invoice:
            return None
        return cls.to_response(invoice)

    @classmethod
    def create(cls, db: Session, data: InvoiceCreate) -> InvoiceResponse:
        """Create a new invoice with auto-calculated amounts."""
        # Check company exists
        company = db.query(Company).filter(Company.gst_number == data.gst_number).first()
        if not company:
            raise ValueError(f"Company with GST {data.gst_number} not found.")

        # Check unique invoice number
        existing = db.query(Invoice).filter(
            Invoice.invoice_number == data.invoice_number.upper()
        ).first()
        if existing:
            raise ValueError(f"Invoice {data.invoice_number} already exists.")

        # Calculate amounts
        amounts = cls.calculate_amounts(
            invoice_amount=data.invoice_amount,
            gst_percentage=data.gst_percentage,
            tds_percentage=data.tds_percentage,
            retention_percentage=data.retention_percentage,
        )

        invoice = Invoice(
            invoice_number=data.invoice_number.upper(),
            gst_number=data.gst_number.upper(),
            invoice_date=data.invoice_date,
            due_date=data.due_date,
            work_description=data.work_description,
            site_location=data.site_location,
            invoice_amount=data.invoice_amount,
            gst_percentage=data.gst_percentage,
            gst_amount=amounts["gst_amount"],
            total_amount=amounts["total_amount"],
            tds_percentage=data.tds_percentage,
            tds_amount=amounts["tds_amount"],
            retention_percentage=data.retention_percentage,
            retention_amount=amounts["retention_amount"],
            net_receivable=amounts["net_receivable"],
            invoice_status=InvoiceStatus.UNPAID.value,
        )

        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        # Re-fetch with relationships
        return cls.get_by_number(db, invoice.invoice_number)

    @classmethod
    def update(cls, db: Session, invoice_number: str, data: InvoiceUpdate) -> Optional[InvoiceResponse]:
        """Update an invoice and recalculate amounts."""
        invoice = db.query(Invoice).filter(
            Invoice.invoice_number == invoice_number.upper()
        ).first()
        if not invoice:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Update basic fields
        for key, value in update_data.items():
            if key not in ("invoice_amount", "gst_percentage", "tds_percentage", "retention_percentage"):
                setattr(invoice, key, value)

        # Recalculate if financial fields changed
        inv_amount = update_data.get("invoice_amount", float(invoice.invoice_amount))
        gst_pct = update_data.get("gst_percentage", float(invoice.gst_percentage))
        tds_pct = update_data.get("tds_percentage", float(invoice.tds_percentage))
        ret_pct = update_data.get("retention_percentage", float(invoice.retention_percentage))

        amounts = cls.calculate_amounts(inv_amount, gst_pct, tds_pct, ret_pct)

        invoice.invoice_amount = inv_amount
        invoice.gst_percentage = gst_pct
        invoice.tds_percentage = tds_pct
        invoice.retention_percentage = ret_pct
        invoice.gst_amount = amounts["gst_amount"]
        invoice.total_amount = amounts["total_amount"]
        invoice.tds_amount = amounts["tds_amount"]
        invoice.retention_amount = amounts["retention_amount"]
        invoice.net_receivable = amounts["net_receivable"]

        # Recalculate status
        total_paid = cls.get_total_paid(invoice)
        invoice.invoice_status = cls.derive_status(amounts["net_receivable"], total_paid)

        db.commit()
        return cls.get_by_number(db, invoice.invoice_number)

    @staticmethod
    def delete(db: Session, invoice_number: str) -> bool:
        """Delete an invoice and all related data."""
        invoice = db.query(Invoice).filter(
            Invoice.invoice_number == invoice_number.upper()
        ).first()
        if not invoice:
            return False
        db.delete(invoice)
        db.commit()
        return True
