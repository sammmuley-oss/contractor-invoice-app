"""Backup service - auto-backup, JSON export, and JSON import."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.document import Document
from app.config import settings


class BackupService:
    """Service for database backup, export, and import operations."""

    @staticmethod
    def get_backup_dir() -> Path:
        """Get or create backup directory."""
        backup_dir = Path(settings.BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir

    @staticmethod
    def create_auto_backup() -> Optional[str]:
        """Create a timestamped copy of the SQLite database file."""
        # Handle both sqlite:///./file.db and sqlite:////data/file.db formats
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite:////"):
            db_path = Path(db_url.replace("sqlite:///", ""))
        else:
            db_path = Path(db_url.replace("sqlite:///./", ""))
        if not db_path.exists():
            return None

        backup_dir = BackupService.get_backup_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}.db"
        backup_path = backup_dir / backup_name

        shutil.copy2(str(db_path), str(backup_path))

        # Clean old backups — keep last 10
        BackupService.cleanup_old_backups(keep=10)

        return backup_name

    @staticmethod
    def cleanup_old_backups(keep: int = 10):
        """Remove old backup files, keeping only the most recent ones."""
        backup_dir = BackupService.get_backup_dir()
        backups = sorted(
            list(backup_dir.glob("backup_*.db")),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for old_backup in backups[keep:]:
            old_backup.unlink()

    @staticmethod
    def list_backups() -> list[dict]:
        """List all available backup files."""
        backup_dir = BackupService.get_backup_dir()
        backups = sorted(
            list(backup_dir.glob("backup_*.db")),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        return [
            {
                "filename": f.name,
                "size": f.stat().st_size,
                "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
            for f in backups
        ]

    @staticmethod
    def export_data(db: Session) -> dict:
        """Export all database data as a JSON-serializable dict."""
        companies = db.query(Company).all()
        invoices = db.query(Invoice).all()
        payments = db.query(Payment).all()
        documents = db.query(Document).all()

        return {
            "export_date": datetime.now().isoformat(),
            "version": "1.0.0",
            "companies": [
                {
                    "gst_number": c.gst_number,
                    "company_name": c.company_name,
                    "contact_person": c.contact_person,
                    "mobile": c.mobile,
                    "email": c.email,
                    "address": c.address,
                    "created_date": c.created_date.isoformat() if c.created_date else None,
                    "updated_date": c.updated_date.isoformat() if c.updated_date else None,
                }
                for c in companies
            ],
            "invoices": [
                {
                    "invoice_number": i.invoice_number,
                    "gst_number": i.gst_number,
                    "invoice_date": i.invoice_date.isoformat() if i.invoice_date else None,
                    "due_date": i.due_date.isoformat() if i.due_date else None,
                    "work_description": i.work_description,
                    "site_location": i.site_location,
                    "invoice_amount": float(i.invoice_amount),
                    "gst_percentage": float(i.gst_percentage),
                    "gst_amount": float(i.gst_amount),
                    "total_amount": float(i.total_amount),
                    "tds_percentage": float(i.tds_percentage),
                    "tds_amount": float(i.tds_amount),
                    "retention_percentage": float(i.retention_percentage),
                    "retention_amount": float(i.retention_amount),
                    "net_receivable": float(i.net_receivable),
                    "invoice_status": i.invoice_status,
                    "created_date": i.created_date.isoformat() if i.created_date else None,
                    "updated_date": i.updated_date.isoformat() if i.updated_date else None,
                }
                for i in invoices
            ],
            "payments": [
                {
                    "payment_id": p.payment_id,
                    "invoice_number": p.invoice_number,
                    "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                    "amount_received": float(p.amount_received),
                    "payment_mode": p.payment_mode,
                    "reference_number": p.reference_number,
                    "remarks": p.remarks,
                    "created_date": p.created_date.isoformat() if p.created_date else None,
                }
                for p in payments
            ],
            "documents": [
                {
                    "document_id": d.document_id,
                    "invoice_number": d.invoice_number,
                    "document_name": d.document_name,
                    "file_path": d.file_path,
                    "file_type": d.file_type,
                    "file_size": d.file_size,
                    "upload_date": d.upload_date.isoformat() if d.upload_date else None,
                }
                for d in documents
            ],
        }

    @staticmethod
    def import_data(db: Session, data: dict) -> dict:
        """Import data from a JSON dict, replacing all existing data."""
        required_keys = {"companies", "invoices", "payments"}
        if not required_keys.issubset(data.keys()):
            raise ValueError(
                f"Invalid backup file. Missing keys: {required_keys - data.keys()}"
            )

        # Clear existing data (order matters — children first for FK constraints)
        db.query(Document).delete()
        db.query(Payment).delete()
        db.query(Invoice).delete()
        db.query(Company).delete()
        db.commit()

        counts = {"companies": 0, "invoices": 0, "payments": 0, "documents": 0}

        # Import companies
        for c in data.get("companies", []):
            company = Company(
                gst_number=c["gst_number"],
                company_name=c["company_name"],
                contact_person=c.get("contact_person"),
                mobile=c.get("mobile"),
                email=c.get("email"),
                address=c.get("address"),
            )
            if c.get("created_date"):
                company.created_date = datetime.fromisoformat(c["created_date"])
            if c.get("updated_date"):
                company.updated_date = datetime.fromisoformat(c["updated_date"])
            db.add(company)
            counts["companies"] += 1
        db.commit()

        # Import invoices
        for i in data.get("invoices", []):
            invoice = Invoice(
                invoice_number=i["invoice_number"],
                gst_number=i["gst_number"],
                invoice_date=datetime.fromisoformat(i["invoice_date"]).date() if i.get("invoice_date") else None,
                due_date=datetime.fromisoformat(i["due_date"]).date() if i.get("due_date") else None,
                work_description=i.get("work_description"),
                site_location=i.get("site_location"),
                invoice_amount=i["invoice_amount"],
                gst_percentage=i["gst_percentage"],
                gst_amount=i["gst_amount"],
                total_amount=i["total_amount"],
                tds_percentage=i["tds_percentage"],
                tds_amount=i["tds_amount"],
                retention_percentage=i["retention_percentage"],
                retention_amount=i["retention_amount"],
                net_receivable=i["net_receivable"],
                invoice_status=i.get("invoice_status", "Unpaid"),
            )
            if i.get("created_date"):
                invoice.created_date = datetime.fromisoformat(i["created_date"])
            if i.get("updated_date"):
                invoice.updated_date = datetime.fromisoformat(i["updated_date"])
            db.add(invoice)
            counts["invoices"] += 1
        db.commit()

        # Import payments
        for p in data.get("payments", []):
            payment = Payment(
                invoice_number=p["invoice_number"],
                payment_date=datetime.fromisoformat(p["payment_date"]).date() if p.get("payment_date") else None,
                amount_received=p["amount_received"],
                payment_mode=p["payment_mode"],
                reference_number=p.get("reference_number"),
                remarks=p.get("remarks"),
            )
            if p.get("created_date"):
                payment.created_date = datetime.fromisoformat(p["created_date"])
            db.add(payment)
            counts["payments"] += 1
        db.commit()

        # Import documents (metadata only — actual files may not exist)
        for d in data.get("documents", []):
            document = Document(
                invoice_number=d["invoice_number"],
                document_name=d["document_name"],
                file_path=d.get("file_path", ""),
                file_type=d.get("file_type"),
                file_size=d.get("file_size"),
            )
            if d.get("upload_date"):
                document.upload_date = datetime.fromisoformat(d["upload_date"])
            db.add(document)
            counts["documents"] += 1
        db.commit()

        return counts
