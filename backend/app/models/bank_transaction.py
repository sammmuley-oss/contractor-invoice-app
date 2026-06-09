"""Bank Transaction model for individual transactions parsed from statements."""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date,
    Numeric, ForeignKey,
)
from sqlalchemy.orm import relationship

from app.database import Base


class BankTransaction(Base):
    """Individual transaction extracted from a bank statement."""

    __tablename__ = "bank_transactions"

    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    statement_id = Column(
        Integer,
        ForeignKey("bank_statements.statement_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    transaction_date = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    credit_amount = Column(Numeric(14, 2), nullable=False, default=0)
    debit_amount = Column(Numeric(14, 2), nullable=False, default=0)

    utr_number = Column(String(100), nullable=True)
    reference_number = Column(String(200), nullable=True)
    sender_name = Column(String(255), nullable=True)

    # Reconciliation fields
    match_status = Column(String(20), nullable=False, default="Unmatched")
    matched_invoice_number = Column(
        String(50),
        ForeignKey("invoices.invoice_number", ondelete="SET NULL"),
        nullable=True,
    )
    confidence_score = Column(Numeric(5, 2), nullable=True)

    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    statement = relationship("BankStatement", back_populates="transactions")
    matched_invoice = relationship("Invoice", foreign_keys=[matched_invoice_number])

    def __repr__(self):
        return (
            f"<BankTransaction(id={self.transaction_id}, "
            f"credit={self.credit_amount}, status='{self.match_status}')>"
        )
