"""Company schemas for validation."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator, Field


GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")


class CompanyCreate(BaseModel):
    """Schema for creating a new company."""

    company_name: str = Field(..., min_length=1, max_length=255)
    gst_number: str = Field(..., min_length=15, max_length=15)
    contact_person: Optional[str] = Field(None, max_length=255)
    mobile: Optional[str] = Field(None, max_length=15)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None

    @field_validator("gst_number")
    @classmethod
    def validate_gst_number(cls, v: str) -> str:
        v = v.upper().strip()
        if not GSTIN_REGEX.match(v):
            raise ValueError(
                "Invalid GST Number format. Must be 15 characters: "
                "2 digits (state) + 10 char PAN + entity number + Z + checksum"
            )
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        # Indian mobile: optional +91, then 10 digits
        cleaned = re.sub(r"[\s\-\+]", "", v)
        if cleaned.startswith("91") and len(cleaned) == 12:
            cleaned = cleaned[2:]
        if not re.match(r"^[6-9]\d{9}$", cleaned):
            raise ValueError("Invalid Indian mobile number. Must be 10 digits starting with 6-9.")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return v
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email address.")
        return v


class CompanyUpdate(BaseModel):
    """Schema for updating a company."""

    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    contact_person: Optional[str] = Field(None, max_length=255)
    mobile: Optional[str] = Field(None, max_length=15)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return v
        v = v.strip()
        cleaned = re.sub(r"[\s\-\+]", "", v)
        if cleaned.startswith("91") and len(cleaned) == 12:
            cleaned = cleaned[2:]
        if not re.match(r"^[6-9]\d{9}$", cleaned):
            raise ValueError("Invalid Indian mobile number.")
        return v


class CompanyResponse(BaseModel):
    """Schema for company API response."""

    gst_number: str
    company_name: str
    contact_person: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    created_date: datetime
    updated_date: datetime
    total_invoices: int = 0
    total_revenue: float = 0
    pending_amount: float = 0

    model_config = {"from_attributes": True}
