"""Payment API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api", tags=["Payments"])


@router.get("/payments", response_model=list[PaymentResponse])
def list_payments(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all payments."""
    return PaymentService.get_all(db, search=search)


@router.get("/invoices/{invoice_number}/payments", response_model=list[PaymentResponse])
def list_invoice_payments(
    invoice_number: str,
    db: Session = Depends(get_db),
):
    """Get payments for a specific invoice."""
    return PaymentService.get_all(db, invoice_number=invoice_number)


@router.post("/invoices/{invoice_number}/payments", response_model=PaymentResponse, status_code=201)
def create_payment(
    invoice_number: str,
    data: PaymentCreate,
    db: Session = Depends(get_db),
):
    """Record a payment against an invoice."""
    try:
        return PaymentService.create(db, invoice_number, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/payments/{payment_id}")
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    """Delete a payment."""
    success = PaymentService.delete(db, payment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return {"message": "Payment deleted successfully."}
