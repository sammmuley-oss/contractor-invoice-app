"""Company API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse
from app.services.company_service import CompanyService

router = APIRouter(prefix="/api/companies", tags=["Companies"])


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all companies with optional search."""
    return CompanyService.get_all(db, search=search)


@router.get("/{gst_number}")
def get_company(gst_number: str, db: Session = Depends(get_db)):
    """Get a company by GST number."""
    company = CompanyService.get_by_gst(db, gst_number)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    # Return with aggregates
    companies = CompanyService.get_all(db)
    for c in companies:
        if c.gst_number == gst_number.upper():
            return c
    raise HTTPException(status_code=404, detail="Company not found.")


@router.post("", response_model=CompanyResponse, status_code=201)
def create_company(data: CompanyCreate, db: Session = Depends(get_db)):
    """Create a new company."""
    try:
        company = CompanyService.create(db, data)
        # Re-fetch with aggregates
        companies = CompanyService.get_all(db)
        for c in companies:
            if c.gst_number == company.gst_number:
                return c
        return company
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{gst_number}", response_model=CompanyResponse)
def update_company(gst_number: str, data: CompanyUpdate, db: Session = Depends(get_db)):
    """Update a company."""
    company = CompanyService.update(db, gst_number, data)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    # Re-fetch with aggregates
    companies = CompanyService.get_all(db)
    for c in companies:
        if c.gst_number == company.gst_number:
            return c
    return company


@router.delete("/{gst_number}")
def delete_company(gst_number: str, db: Session = Depends(get_db)):
    """Delete a company and all related data."""
    success = CompanyService.delete(db, gst_number)
    if not success:
        raise HTTPException(status_code=404, detail="Company not found.")
    return {"message": "Company deleted successfully."}
