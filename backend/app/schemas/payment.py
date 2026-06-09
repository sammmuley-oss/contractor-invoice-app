"""Payment schemas."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    """Schema for recording a payment."""

    payment_date: date
    amount_received: float = Field(..., gt=0)
    payment_mode: str = Field(..., min_length=1, max_length=50)
    reference_number: Optional[str] = Field(None, max_length=100)
    remarks: Optional[str] = None


class PaymentResponse(BaseModel):
    """Payment API response."""

    payment_id: int
    invoice_number: str
    payment_date: date
    amount_received: float
    payment_mode: str
    reference_number: Optional[str] = None
    remarks: Optional[str] = None
    created_date: datetime

    # Include invoice context
    company_name: str = ""
    gst_number: str = ""
    net_receivable: float = 0
    invoice_status: str = ""

    model_config = {"from_attributes": True}
