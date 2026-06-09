"""Dashboard and Reports API endpoints."""

from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.report_service import ReportService

router = APIRouter(prefix="/api", tags=["Dashboard & Reports"])


# ─── Dashboard ────────────────────────────────────────────

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get all dashboard statistics."""
    return ReportService.get_dashboard_stats(db)


@router.get("/dashboard/recent-invoices")
def get_recent_invoices(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get most recent invoices."""
    return ReportService.get_recent_invoices(db, limit=limit)


@router.get("/dashboard/upcoming-dues")
def get_upcoming_dues(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get upcoming due payments."""
    return ReportService.get_upcoming_dues(db, limit=limit)


@router.get("/dashboard/revenue-trend")
def get_revenue_trend(
    year: int = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get monthly revenue trend for charts."""
    if year is None:
        year = date.today().year
    return ReportService.get_monthly_revenue_trend(db, year)


# ─── Reports ──────────────────────────────────────────────

@router.get("/reports/monthly")
def get_monthly_report(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Generate monthly report."""
    return ReportService.get_monthly_report(db, year, month)


@router.get("/reports/yearly")
def get_yearly_report(
    year: int = Query(...),
    db: Session = Depends(get_db),
):
    """Generate yearly report with month-wise breakdown."""
    return ReportService.get_yearly_report(db, year)


@router.get("/reports/company")
def get_company_report(
    gst_number: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Generate company-wise report."""
    return ReportService.get_company_report(db, gst_number)


# ─── Search ───────────────────────────────────────────────

@router.get("/search")
def global_search(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    """Global search across companies, invoices, and payments."""
    from app.services.company_service import CompanyService
    from app.services.invoice_service import InvoiceService
    from app.services.payment_service import PaymentService

    companies = CompanyService.get_all(db, search=q)
    invoices_result = InvoiceService.get_all(db, search=q, page_size=10)
    payments = PaymentService.get_all(db, search=q)

    return {
        "companies": [
            {
                "gst_number": c.gst_number,
                "company_name": c.company_name,
                "contact_person": c.contact_person,
            }
            for c in companies[:5]
        ],
        "invoices": [
            {
                "invoice_number": i.invoice_number,
                "company_name": i.company_name,
                "total_amount": i.total_amount,
                "invoice_status": i.invoice_status,
            }
            for i in invoices_result.items[:5]
        ],
        "payments": [
            {
                "payment_id": p.payment_id,
                "invoice_number": p.invoice_number,
                "amount_received": p.amount_received,
                "payment_mode": p.payment_mode,
            }
            for p in payments[:5]
        ],
    }
