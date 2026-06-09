"""Invoice API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceListResponse
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])


@router.get("", response_model=InvoiceListResponse)
def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    gst_number: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None),
    sort_by: str = Query("invoice_date"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
):
    """Get paginated invoices with filters."""
    return InvoiceService.get_all(
        db,
        page=page,
        page_size=page_size,
        gst_number=gst_number,
        status=status,
        search=search,
        month=month,
        year=year,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{invoice_number}", response_model=InvoiceResponse)
def get_invoice(invoice_number: str, db: Session = Depends(get_db)):
    """Get a single invoice with all details."""
    invoice = InvoiceService.get_by_number(db, invoice_number)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice(data: InvoiceCreate, db: Session = Depends(get_db)):
    """Create a new invoice with auto-calculated amounts."""
    try:
        return InvoiceService.create(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{invoice_number}", response_model=InvoiceResponse)
def update_invoice(invoice_number: str, data: InvoiceUpdate, db: Session = Depends(get_db)):
    """Update an invoice and recalculate amounts."""
    result = InvoiceService.update(db, invoice_number, data)
    if not result:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return result


@router.delete("/{invoice_number}")
def delete_invoice(invoice_number: str, db: Session = Depends(get_db)):
    """Delete an invoice and all related data."""
    success = InvoiceService.delete(db, invoice_number)
    if not success:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return {"message": "Invoice deleted successfully."}


@router.post("/calculate-preview")
def calculate_preview(
    invoice_amount: float = Query(..., gt=0),
    gst_percentage: float = Query(18.0, ge=0),
    tds_percentage: float = Query(0.0, ge=0),
    retention_percentage: float = Query(0.0, ge=0),
):
    """Preview calculation without saving (for live form preview)."""
    return InvoiceService.calculate_amounts(
        invoice_amount=invoice_amount,
        gst_percentage=gst_percentage,
        tds_percentage=tds_percentage,
        retention_percentage=retention_percentage,
    )
