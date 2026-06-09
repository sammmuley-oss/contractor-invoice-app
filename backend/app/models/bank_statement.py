"""Bank Statement model for tracking uploaded statements."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Date
from sqlalchemy.orm import relationship

from app.database import Base


class BankStatement(Base):
    """Uploaded bank statement metadata."""

    __tablename__ = "bank_statements"

    statement_id = Column(Integer, primary_key=True, autoincrement=True)
    bank_name = Column(String(100), nullable=False)
    file_name = Column(String(500), nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    statement_start_date = Column(Date, nullable=True)
    statement_end_date = Column(Date, nullable=True)
    total_transactions = Column(Integer, default=0)
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    transactions = relationship(
        "BankTransaction",
        back_populates="statement",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<BankStatement(id={self.statement_id}, bank='{self.bank_name}')>"
