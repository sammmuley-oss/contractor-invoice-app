"""Report service - generates monthly, yearly, and company-wise reports."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import extract, func

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.company import Company
from app.utils.indian_currency import round_decimal


class ReportService:
    """Service layer for report generation."""

    @staticmethod
    def get_dashboard_stats(db: Session) -> dict:
        """Get all dashboard statistics."""
        today = date.today()
        current_month = today.month
        current_year = today.year

        # Total companies
        total_companies = db.query(func.count(Company.gst_number)).scalar() or 0

        # Invoice stats
        all_invoices = db.query(Invoice).options(joinedload(Invoice.payments)).all()
        total_invoices = len(all_invoices)

        paid_count = 0
        unpaid_count = 0
        partially_paid_count = 0
        total_revenue = 0.0
        pending_revenue = 0.0
        total_tds = 0.0
        total_retention = 0.0
        this_month_revenue = 0.0
        this_year_revenue = 0.0

        for inv in all_invoices:
            net_receivable = float(inv.net_receivable or 0)
            total_paid_for_inv = sum(float(p.amount_received or 0) for p in inv.payments)
            pending = round_decimal(net_receivable - total_paid_for_inv)
            if pending < 0:
                pending = 0

            total_revenue += net_receivable
            pending_revenue += pending
            total_tds += float(inv.tds_amount or 0)
            total_retention += float(inv.retention_amount or 0)

            if inv.invoice_status == InvoiceStatus.PAID.value:
                paid_count += 1
            elif inv.invoice_status == InvoiceStatus.PARTIALLY_PAID.value:
                partially_paid_count += 1
            else:
                unpaid_count += 1

            # This month / this year
            inv_date = inv.invoice_date
            if inv_date and inv_date.year == current_year:
                this_year_revenue += net_receivable
                if inv_date.month == current_month:
                    this_month_revenue += net_receivable

        return {
            "total_companies": total_companies,
            "total_invoices": total_invoices,
            "paid_invoices": paid_count,
            "unpaid_invoices": unpaid_count,
            "partially_paid_invoices": partially_paid_count,
            "pending_invoices": unpaid_count + partially_paid_count,
            "total_revenue": round_decimal(total_revenue),
            "pending_revenue": round_decimal(pending_revenue),
            "paid_revenue": round_decimal(total_revenue - pending_revenue),
            "this_month_revenue": round_decimal(this_month_revenue),
            "this_year_revenue": round_decimal(this_year_revenue),
            "tds_deducted": round_decimal(total_tds),
            "retention_outstanding": round_decimal(total_retention),
        }

    @staticmethod
    def get_recent_invoices(db: Session, limit: int = 10) -> list[dict]:
        """Get the most recent invoices."""
        invoices = (
            db.query(Invoice)
            .options(joinedload(Invoice.company), joinedload(Invoice.payments))
            .order_by(Invoice.created_date.desc())
            .limit(limit)
            .all()
        )

        result = []
        seen = set()
        for inv in invoices:
            if inv.invoice_number in seen:
                continue
            seen.add(inv.invoice_number)
            total_paid = sum(float(p.amount_received or 0) for p in inv.payments)
            result.append({
                "invoice_number": inv.invoice_number,
                "company_name": inv.company.company_name if inv.company else "",
                "gst_number": inv.gst_number,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else "",
                "due_date": inv.due_date.isoformat() if inv.due_date else "",
                "total_amount": float(inv.total_amount or 0),
                "net_receivable": float(inv.net_receivable or 0),
                "total_paid": total_paid,
                "pending_amount": round_decimal(float(inv.net_receivable or 0) - total_paid),
                "invoice_status": inv.invoice_status,
            })
        return result

    @staticmethod
    def get_upcoming_dues(db: Session, limit: int = 10) -> list[dict]:
        """Get invoices with upcoming due dates that are not fully paid."""
        today = date.today()
        invoices = (
            db.query(Invoice)
            .options(joinedload(Invoice.company), joinedload(Invoice.payments))
            .filter(
                Invoice.invoice_status.in_([InvoiceStatus.UNPAID.value, InvoiceStatus.PARTIALLY_PAID.value])
            )
            .order_by(Invoice.due_date.asc())
            .limit(limit * 2)  # fetch more to deduplicate
            .all()
        )

        result = []
        seen = set()
        for inv in invoices:
            if inv.invoice_number in seen:
                continue
            seen.add(inv.invoice_number)
            total_paid = sum(float(p.amount_received or 0) for p in inv.payments)
            net_receivable = float(inv.net_receivable or 0)
            pending = round_decimal(net_receivable - total_paid)

            days_until_due = (inv.due_date - today).days if inv.due_date else 0

            result.append({
                "invoice_number": inv.invoice_number,
                "company_name": inv.company.company_name if inv.company else "",
                "due_date": inv.due_date.isoformat() if inv.due_date else "",
                "net_receivable": net_receivable,
                "pending_amount": pending,
                "days_until_due": days_until_due,
                "is_overdue": days_until_due < 0,
                "invoice_status": inv.invoice_status,
            })

            if len(result) >= limit:
                break

        return result

    @staticmethod
    def get_monthly_report(db: Session, year: int, month: int) -> dict:
        """Generate monthly report."""
        invoices = (
            db.query(Invoice)
            .options(joinedload(Invoice.payments), joinedload(Invoice.company))
            .filter(
                extract("year", Invoice.invoice_date) == year,
                extract("month", Invoice.invoice_date) == month,
            )
            .all()
        )

        total_invoices = 0
        total_revenue = 0.0
        total_paid = 0.0
        total_tds = 0.0
        total_retention = 0.0
        invoice_details = []

        seen = set()
        for inv in invoices:
            if inv.invoice_number in seen:
                continue
            seen.add(inv.invoice_number)

            total_invoices += 1
            net_receivable = float(inv.net_receivable or 0)
            paid_amount = sum(float(p.amount_received or 0) for p in inv.payments)

            total_revenue += net_receivable
            total_paid += paid_amount
            total_tds += float(inv.tds_amount or 0)
            total_retention += float(inv.retention_amount or 0)

            invoice_details.append({
                "invoice_number": inv.invoice_number,
                "company_name": inv.company.company_name if inv.company else "",
                "invoice_date": inv.invoice_date.isoformat(),
                "invoice_amount": float(inv.invoice_amount or 0),
                "gst_amount": float(inv.gst_amount or 0),
                "total_amount": float(inv.total_amount or 0),
                "tds_amount": float(inv.tds_amount or 0),
                "retention_amount": float(inv.retention_amount or 0),
                "net_receivable": net_receivable,
                "total_paid": paid_amount,
                "pending": round_decimal(net_receivable - paid_amount),
                "status": inv.invoice_status,
            })

        return {
            "year": year,
            "month": month,
            "total_invoices": total_invoices,
            "total_revenue": round_decimal(total_revenue),
            "total_paid": round_decimal(total_paid),
            "pending_revenue": round_decimal(total_revenue - total_paid),
            "tds_deducted": round_decimal(total_tds),
            "retention_amount": round_decimal(total_retention),
            "invoices": invoice_details,
        }

    @staticmethod
    def get_yearly_report(db: Session, year: int) -> dict:
        """Generate yearly report with month-wise breakdown."""
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        monthly_data = []
        annual_revenue = 0.0
        annual_paid = 0.0
        annual_tds = 0.0
        annual_retention = 0.0
        annual_invoices = 0

        for month_num in range(1, 13):
            invoices = (
                db.query(Invoice)
                .options(joinedload(Invoice.payments))
                .filter(
                    extract("year", Invoice.invoice_date) == year,
                    extract("month", Invoice.invoice_date) == month_num,
                )
                .all()
            )

            month_revenue = 0.0
            month_paid = 0.0
            month_tds = 0.0
            month_retention = 0.0
            month_count = 0

            seen = set()
            for inv in invoices:
                if inv.invoice_number in seen:
                    continue
                seen.add(inv.invoice_number)
                month_count += 1
                net_receivable = float(inv.net_receivable or 0)
                paid = sum(float(p.amount_received or 0) for p in inv.payments)

                month_revenue += net_receivable
                month_paid += paid
                month_tds += float(inv.tds_amount or 0)
                month_retention += float(inv.retention_amount or 0)

            monthly_data.append({
                "month": months[month_num - 1],
                "month_number": month_num,
                "invoice_count": month_count,
                "revenue": round_decimal(month_revenue),
                "paid": round_decimal(month_paid),
                "pending": round_decimal(month_revenue - month_paid),
                "tds": round_decimal(month_tds),
                "retention": round_decimal(month_retention),
            })

            annual_revenue += month_revenue
            annual_paid += month_paid
            annual_tds += month_tds
            annual_retention += month_retention
            annual_invoices += month_count

        return {
            "year": year,
            "total_invoices": annual_invoices,
            "total_revenue": round_decimal(annual_revenue),
            "total_paid": round_decimal(annual_paid),
            "total_pending": round_decimal(annual_revenue - annual_paid),
            "total_tds": round_decimal(annual_tds),
            "total_retention": round_decimal(annual_retention),
            "monthly_data": monthly_data,
        }

    @staticmethod
    def get_company_report(db: Session, gst_number: Optional[str] = None) -> list[dict]:
        """Generate company-wise report."""
        query = db.query(Company)
        if gst_number:
            query = query.filter(Company.gst_number == gst_number.upper())

        companies = query.order_by(Company.company_name).all()
        result = []

        for company in companies:
            invoices = (
                db.query(Invoice)
                .options(joinedload(Invoice.payments))
                .filter(Invoice.gst_number == company.gst_number)
                .all()
            )

            total_invoices = 0
            total_revenue = 0.0
            total_paid_amt = 0.0
            total_tds = 0.0
            total_retention = 0.0

            seen = set()
            for inv in invoices:
                if inv.invoice_number in seen:
                    continue
                seen.add(inv.invoice_number)
                total_invoices += 1
                net_receivable = float(inv.net_receivable or 0)
                paid = sum(float(p.amount_received or 0) for p in inv.payments)

                total_revenue += net_receivable
                total_paid_amt += paid
                total_tds += float(inv.tds_amount or 0)
                total_retention += float(inv.retention_amount or 0)

            result.append({
                "company_name": company.company_name,
                "gst_number": company.gst_number,
                "total_invoices": total_invoices,
                "total_revenue": round_decimal(total_revenue),
                "total_paid": round_decimal(total_paid_amt),
                "total_pending": round_decimal(total_revenue - total_paid_amt),
                "tds_deducted": round_decimal(total_tds),
                "retention_held": round_decimal(total_retention),
            })

        return result

    @staticmethod
    def get_monthly_revenue_trend(db: Session, year: int) -> list[dict]:
        """Get revenue trend data for charts (month-wise for a given year)."""
        months = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ]

        trend = []
        for month_num in range(1, 13):
            invoices = (
                db.query(Invoice)
                .options(joinedload(Invoice.payments))
                .filter(
                    extract("year", Invoice.invoice_date) == year,
                    extract("month", Invoice.invoice_date) == month_num,
                )
                .all()
            )

            revenue = 0.0
            paid = 0.0
            seen = set()
            for inv in invoices:
                if inv.invoice_number in seen:
                    continue
                seen.add(inv.invoice_number)
                revenue += float(inv.net_receivable or 0)
                paid += sum(float(p.amount_received or 0) for p in inv.payments)

            trend.append({
                "month": months[month_num - 1],
                "revenue": round_decimal(revenue),
                "paid": round_decimal(paid),
                "pending": round_decimal(revenue - paid),
            })

        return trend
