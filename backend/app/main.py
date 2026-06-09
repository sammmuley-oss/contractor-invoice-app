"""FastAPI Application Entry Point - Contractor Invoice Management."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import create_tables
from app.api import companies, invoices, payments, documents, dashboard, backup, bank_statements, reconciliation

# Static files directory
STATIC_DIR = Path(__file__).parent.parent / "static"

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Invoice Management System for Indian Contractors",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(companies.router)
app.include_router(invoices.router)
app.include_router(payments.router)
app.include_router(documents.router)
app.include_router(dashboard.router)
app.include_router(backup.router)
app.include_router(bank_statements.router)
app.include_router(reconciliation.router)


@app.on_event("startup")
def startup():
    """Create database tables on startup."""
    create_tables()
    print(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION} started!")
    print(f"[DB] Database: {settings.DATABASE_URL}")
    print(f"[DIR] Uploads: {settings.UPLOAD_DIR}")
    print(f"[DIR] Backups: {settings.BACKUP_DIR}")

    # Auto-backup on startup
    from app.services.backup_service import BackupService
    try:
        backup_name = BackupService.create_auto_backup()
        if backup_name:
            print(f"[BACKUP] Auto-backup created: {backup_name}")
    except Exception as e:
        print(f"[WARN] Auto-backup failed: {e}")

    # Seed sample data for development
    _seed_sample_data()


def _seed_sample_data():
    """Add sample data if the database is empty (dev only)."""
    if not settings.DEBUG:
        return

    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.invoice import Invoice
    from app.services.invoice_service import InvoiceService
    from app.schemas.invoice import InvoiceCreate
    from app.schemas.company import CompanyCreate
    from datetime import date, timedelta

    db = SessionLocal()
    try:
        # Only seed if no companies exist
        if db.query(Company).count() > 0:
            return

        print("[SEED] Seeding sample data...")

        # Sample companies
        sample_companies = [
            CompanyCreate(
                company_name="Tata Consultancy Services",
                gst_number="27AAACT2727Q1ZV",
                contact_person="Rajesh Kumar",
                mobile="9876543210",
                email="rajesh@tcs.com",
                address="TCS House, Raveline Street, Fort, Mumbai 400001",
            ),
            CompanyCreate(
                company_name="Infosys Limited",
                gst_number="29AABCI1234F1ZP",
                contact_person="Priya Sharma",
                mobile="9876543211",
                email="priya@infosys.com",
                address="Electronics City, Hosur Road, Bangalore 560100",
            ),
            CompanyCreate(
                company_name="Wipro Technologies",
                gst_number="29AABCW8574F1Z2",
                contact_person="Amit Patel",
                mobile="9876543212",
                email="amit@wipro.com",
                address="Doddakannelli, Sarjapur Road, Bangalore 560035",
            ),
            CompanyCreate(
                company_name="Larsen & Toubro Limited",
                gst_number="27AABCL0605F1ZI",
                contact_person="Suresh Menon",
                mobile="9876543213",
                email="suresh@lt.com",
                address="L&T House, Ballard Estate, Mumbai 400001",
            ),
            CompanyCreate(
                company_name="HCL Technologies",
                gst_number="09AABCH1234F1Z5",
                contact_person="Deepa Nair",
                mobile="9876543214",
                email="deepa@hcl.com",
                address="Technology Hub, Sector 126, Noida 201301",
            ),
        ]

        from app.services.company_service import CompanyService
        for comp_data in sample_companies:
            try:
                CompanyService.create(db, comp_data)
            except ValueError:
                pass

        # Sample invoices
        today = date.today()
        sample_invoices = [
            InvoiceCreate(
                invoice_number="INV-2026-001",
                gst_number="27AAACT2727Q1ZV",
                invoice_date=today - timedelta(days=45),
                due_date=today - timedelta(days=15),
                work_description="Software Development - Phase 1",
                site_location="Mumbai Office",
                invoice_amount=500000,
                gst_percentage=18,
                tds_percentage=10,
                retention_percentage=5,
            ),
            InvoiceCreate(
                invoice_number="INV-2026-002",
                gst_number="29AABCI1234F1ZP",
                invoice_date=today - timedelta(days=30),
                due_date=today + timedelta(days=15),
                work_description="Cloud Infrastructure Setup",
                site_location="Bangalore DC",
                invoice_amount=750000,
                gst_percentage=18,
                tds_percentage=10,
                retention_percentage=5,
            ),
            InvoiceCreate(
                invoice_number="INV-2026-003",
                gst_number="29AABCW8574F1Z2",
                invoice_date=today - timedelta(days=20),
                due_date=today + timedelta(days=25),
                work_description="Network Security Audit",
                site_location="Wipro Campus, Sarjapur",
                invoice_amount=300000,
                gst_percentage=18,
                tds_percentage=2,
                retention_percentage=0,
            ),
            InvoiceCreate(
                invoice_number="INV-2026-004",
                gst_number="27AABCL0605F1ZI",
                invoice_date=today - timedelta(days=60),
                due_date=today - timedelta(days=30),
                work_description="Civil Engineering Consultation",
                site_location="L&T ECC Site, Powai",
                invoice_amount=1200000,
                gst_percentage=18,
                tds_percentage=10,
                retention_percentage=10,
            ),
            InvoiceCreate(
                invoice_number="INV-2026-005",
                gst_number="09AABCH1234F1Z5",
                invoice_date=today - timedelta(days=10),
                due_date=today + timedelta(days=35),
                work_description="DevOps Pipeline Implementation",
                site_location="HCL Noida Campus",
                invoice_amount=450000,
                gst_percentage=18,
                tds_percentage=10,
                retention_percentage=5,
            ),
            InvoiceCreate(
                invoice_number="INV-2026-006",
                gst_number="27AAACT2727Q1ZV",
                invoice_date=today - timedelta(days=5),
                due_date=today + timedelta(days=40),
                work_description="Software Development - Phase 2",
                site_location="TCS Pune Center",
                invoice_amount=680000,
                gst_percentage=18,
                tds_percentage=10,
                retention_percentage=5,
            ),
        ]

        for inv_data in sample_invoices:
            try:
                InvoiceService.create(db, inv_data)
            except ValueError:
                pass

        # Sample payments
        from app.schemas.payment import PaymentCreate
        from app.services.payment_service import PaymentService

        sample_payments = [
            ("INV-2026-001", PaymentCreate(
                payment_date=today - timedelta(days=10),
                amount_received=400000,
                payment_mode="NEFT/RTGS",
                reference_number="NEFT20260501001",
                remarks="Partial payment for Phase 1",
            )),
            ("INV-2026-004", PaymentCreate(
                payment_date=today - timedelta(days=25),
                amount_received=1132800,
                payment_mode="Bank Transfer",
                reference_number="BT20260415001",
                remarks="Full payment received",
            )),
            ("INV-2026-003", PaymentCreate(
                payment_date=today - timedelta(days=5),
                amount_received=200000,
                payment_mode="UPI",
                reference_number="UPI20260520001",
                remarks="First installment",
            )),
        ]

        for inv_num, payment_data in sample_payments:
            try:
                PaymentService.create(db, inv_num, payment_data)
            except ValueError:
                pass

        print("[OK] Sample data seeded successfully!")

    except Exception as e:
        print(f"[WARN] Seed data error: {e}")
    finally:
        db.close()


# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root():
    """Serve the frontend application."""
    return FileResponse(str(STATIC_DIR / "index.html"))
