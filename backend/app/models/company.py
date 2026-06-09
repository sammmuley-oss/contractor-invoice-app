"""Company model - Uses GST Number as primary key."""

from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.orm import relationship

from app.database import Base


class Company(Base):
    """Company entity identified by GST Number."""

    __tablename__ = "companies"

    gst_number = Column(String(15), primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    contact_person = Column(String(255), nullable=True)
    mobile = Column(String(15), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    invoices = relationship("Invoice", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company(gst_number='{self.gst_number}', name='{self.company_name}')>"
