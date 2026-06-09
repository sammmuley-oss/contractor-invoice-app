"""Payment model for tracking invoice payments."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Payment(Base):
    """Payment record against an invoice."""

    __tablename__ = "payments"

    payment_id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_number = Column(String(50), ForeignKey("invoices.invoice_number", ondelete="CASCADE"), nullable=False, index=True)

    payment_date = Column(Date, nullable=False)
    amount_received = Column(Numeric(14, 2), nullable=False)
    payment_mode = Column(String(50), nullable=False)  # Bank Transfer, Cheque, UPI, Cash, NEFT/RTGS
    reference_number = Column(String(100), nullable=True)
    remarks = Column(Text, nullable=True)

    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    invoice = relationship("Invoice", back_populates="payments")

    def __repr__(self):
        return f"<Payment(id={self.payment_id}, amount={self.amount_received})>"
