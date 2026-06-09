"""Document schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """Document API response."""

    document_id: int
    invoice_number: str
    document_name: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    upload_date: datetime

    model_config = {"from_attributes": True}
