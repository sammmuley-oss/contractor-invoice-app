"""Invoice model with calculation fields."""

from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Date, Numeric, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class InvoiceStatus(str, enum.Enum):
    """Invoice payment status."""
    UNPAID = "Unpaid"
    PARTIALLY_PAID = "Partially Paid"
    PAID = "Paid"


class Invoice(Base):
    """Invoice entity with auto-calculated financial fields."""

    __tablename__ = "invoices"

    invoice_number = Column(String(50), primary_key=True, index=True)
    gst_number = Column(String(15), ForeignKey("companies.gst_number", ondelete="CASCADE"), nullable=False, index=True)

    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    work_description = Column(Text, nullable=True)
    site_location = Column(String(500), nullable=True)

    # Financial fields
    invoice_amount = Column(Numeric(14, 2), nullable=False, default=0)
    gst_percentage = Column(Numeric(5, 2), nullable=False, default=18)
    gst_amount = Column(Numeric(14, 2), nullable=False, default=0)
    total_amount = Column(Numeric(14, 2), nullable=False, default=0)

    tds_percentage = Column(Numeric(5, 2), nullable=False, default=0)
    tds_amount = Column(Numeric(14, 2), nullable=False, default=0)

    retention_percentage = Column(Numeric(5, 2), nullable=False, default=0)
    retention_amount = Column(Numeric(14, 2), nullable=False, default=0)

    net_receivable = Column(Numeric(14, 2), nullable=False, default=0)

    invoice_status = Column(String(20), nullable=False, default=InvoiceStatus.UNPAID.value)

    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="invoice", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Invoice(number='{self.invoice_number}', status='{self.invoice_status}')>"
