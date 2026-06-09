"""Document model for file attachments to invoices."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Document(Base):
    """Document attachment linked to an invoice."""

    __tablename__ = "documents"

    document_id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_number = Column(String(50), ForeignKey("invoices.invoice_number", ondelete="CASCADE"), nullable=False, index=True)

    document_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=True)
    file_size = Column(Integer, nullable=True)  # in bytes

    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    invoice = relationship("Invoice", back_populates="documents")

    def __repr__(self):
        return f"<Document(id={self.document_id}, name='{self.document_name}')>"
