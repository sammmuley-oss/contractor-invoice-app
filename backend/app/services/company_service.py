"""Company service - business logic for company operations."""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.company import Company
from app.models.invoice import Invoice
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse


class CompanyService:
    """Service layer for company CRUD operations."""

    @staticmethod
    def get_all(db: Session, search: Optional[str] = None) -> list[CompanyResponse]:
        """Get all companies with optional search."""
        query = db.query(Company)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Company.company_name.ilike(search_term)) |
                (Company.gst_number.ilike(search_term)) |
                (Company.contact_person.ilike(search_term))
            )

        companies = query.order_by(Company.company_name).all()

        result = []
        for company in companies:
            # Calculate aggregates
            invoices = db.query(Invoice).filter(Invoice.gst_number == company.gst_number).all()
            total_revenue = sum(float(inv.net_receivable or 0) for inv in invoices)
            total_paid = 0
            for inv in invoices:
                paid = sum(float(p.amount_received or 0) for p in inv.payments)
                total_paid += paid

            result.append(CompanyResponse(
                gst_number=company.gst_number,
                company_name=company.company_name,
                contact_person=company.contact_person,
                mobile=company.mobile,
                email=company.email,
                address=company.address,
                created_date=company.created_date,
                updated_date=company.updated_date,
                total_invoices=len(invoices),
                total_revenue=total_revenue,
                pending_amount=total_revenue - total_paid,
            ))

        return result

    @staticmethod
    def get_by_gst(db: Session, gst_number: str) -> Optional[Company]:
        """Get a company by GST number."""
        return db.query(Company).filter(Company.gst_number == gst_number.upper()).first()

    @staticmethod
    def create(db: Session, data: CompanyCreate) -> Company:
        """Create a new company."""
        existing = db.query(Company).filter(Company.gst_number == data.gst_number).first()
        if existing:
            raise ValueError("Company already exists.")

        company = Company(
            gst_number=data.gst_number,
            company_name=data.company_name,
            contact_person=data.contact_person,
            mobile=data.mobile,
            email=data.email,
            address=data.address,
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        return company

    @staticmethod
    def update(db: Session, gst_number: str, data: CompanyUpdate) -> Optional[Company]:
        """Update an existing company."""
        company = db.query(Company).filter(Company.gst_number == gst_number.upper()).first()
        if not company:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(company, key, value)

        db.commit()
        db.refresh(company)
        return company

    @staticmethod
    def delete(db: Session, gst_number: str) -> bool:
        """Delete a company and all related data."""
        company = db.query(Company).filter(Company.gst_number == gst_number.upper()).first()
        if not company:
            return False

        db.delete(company)
        db.commit()
        return True
