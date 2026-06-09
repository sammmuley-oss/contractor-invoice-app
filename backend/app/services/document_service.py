"""Document service - file upload and management."""

import os
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.models.document import Document
from app.models.invoice import Invoice
from app.schemas.document import DocumentResponse
from app.config import settings


class DocumentService:
    """Service layer for document operations."""

    @staticmethod
    def get_by_invoice(db: Session, invoice_number: str) -> list[DocumentResponse]:
        """Get all documents for an invoice."""
        docs = (
            db.query(Document)
            .filter(Document.invoice_number == invoice_number.upper())
            .order_by(Document.upload_date.desc())
            .all()
        )
        return [DocumentResponse.model_validate(d) for d in docs]

    @staticmethod
    async def upload(
        db: Session,
        invoice_number: str,
        file: UploadFile,
    ) -> DocumentResponse:
        """Upload a document and attach it to an invoice."""
        # Verify invoice exists
        invoice = db.query(Invoice).filter(
            Invoice.invoice_number == invoice_number.upper()
        ).first()
        if not invoice:
            raise ValueError(f"Invoice {invoice_number} not found.")

        # Validate file extension
        ext = Path(file.filename).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"File type '{ext}' not allowed. "
                f"Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        # Read file content
        content = await file.read()
        file_size = len(content)

        # Check file size
        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            raise ValueError(
                f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds "
                f"maximum allowed size ({settings.MAX_UPLOAD_SIZE_MB} MB)."
            )

        # Generate unique filename
        unique_name = f"{uuid.uuid4().hex}{ext}"
        # Organize by invoice number
        invoice_dir = os.path.join(settings.UPLOAD_DIR, invoice_number.upper())
        os.makedirs(invoice_dir, exist_ok=True)
        file_path = os.path.join(invoice_dir, unique_name)

        # Write file
        with open(file_path, "wb") as f:
            f.write(content)

        # Create database record
        document = Document(
            invoice_number=invoice_number.upper(),
            document_name=file.filename,
            file_path=file_path,
            file_type=ext,
            file_size=file_size,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return DocumentResponse.model_validate(document)

    @staticmethod
    def get_by_id(db: Session, document_id: int) -> Optional[Document]:
        """Get a document record by ID."""
        return db.query(Document).filter(Document.document_id == document_id).first()

    @staticmethod
    def delete(db: Session, document_id: int) -> bool:
        """Delete a document record and its file."""
        document = db.query(Document).filter(Document.document_id == document_id).first()
        if not document:
            return False

        # Delete file from disk
        if os.path.exists(document.file_path):
            os.remove(document.file_path)

        db.delete(document)
        db.commit()
        return True
