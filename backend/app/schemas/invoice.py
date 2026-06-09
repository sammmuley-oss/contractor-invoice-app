"""Invoice schemas for validation and response."""

from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator, model_validator


class InvoiceCreate(BaseModel):
    """Schema for creating a new invoice."""

    invoice_number: str = Field(..., min_length=1, max_length=50)
    gst_number: str = Field(..., min_length=15, max_length=15)
    invoice_date: date
    due_date: date
    work_description: Optional[str] = None
    site_location: Optional[str] = Field(None, max_length=500)

    invoice_amount: float = Field(..., gt=0)
    gst_percentage: float = Field(default=18.0, ge=0, le=100)
    tds_percentage: float = Field(default=0.0, ge=0, le=100)
    retention_percentage: float = Field(default=0.0, ge=0, le=100)

    @field_validator("invoice_number")
    @classmethod
    def clean_invoice_number(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_dates(self):
        if self.due_date < self.invoice_date:
            raise ValueError("Due date cannot be before invoice date.")
        return self


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice."""

    gst_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    work_description: Optional[str] = None
    site_location: Optional[str] = None

    invoice_amount: Optional[float] = Field(None, gt=0)
    gst_percentage: Optional[float] = Field(None, ge=0, le=100)
    tds_percentage: Optional[float] = Field(None, ge=0, le=100)
    retention_percentage: Optional[float] = Field(None, ge=0, le=100)


class PaymentSummary(BaseModel):
    """Nested payment summary inside invoice response."""

    payment_id: int
    payment_date: date
    amount_received: float
    payment_mode: str
    reference_number: Optional[str] = None
    remarks: Optional[str] = None

    model_config = {"from_attributes": True}


class DocumentSummary(BaseModel):
    """Nested document summary inside invoice response."""

    document_id: int
    document_name: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    upload_date: datetime

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    """Full invoice response with computed fields."""

    invoice_number: str
    gst_number: str
    company_name: str = ""
    invoice_date: date
    due_date: date
    work_description: Optional[str] = None
    site_location: Optional[str] = None

    invoice_amount: float
    gst_percentage: float
    gst_amount: float
    total_amount: float
    tds_percentage: float
    tds_amount: float
    retention_percentage: float
    retention_amount: float
    net_receivable: float

    total_paid: float = 0
    pending_amount: float = 0

    invoice_status: str
    created_date: datetime
    updated_date: datetime

    payments: List[PaymentSummary] = []
    documents: List[DocumentSummary] = []

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    """Paginated list of invoices."""

    items: List[InvoiceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
