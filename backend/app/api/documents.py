"""Document API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api", tags=["Documents"])


@router.get("/invoices/{invoice_number}/documents", response_model=list[DocumentResponse])
def list_invoice_documents(invoice_number: str, db: Session = Depends(get_db)):
    """Get all documents for an invoice."""
    return DocumentService.get_by_invoice(db, invoice_number)


@router.post("/invoices/{invoice_number}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    invoice_number: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a document to an invoice."""
    try:
        return await DocumentService.upload(db, invoice_number, file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/documents/{document_id}")
def download_document(document_id: int, db: Session = Depends(get_db)):
    """Download a document file."""
    document = DocumentService.get_by_id(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    import os
    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")

    return FileResponse(
        path=document.file_path,
        filename=document.document_name,
        media_type="application/octet-stream",
    )


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document."""
    success = DocumentService.delete(db, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": "Document deleted successfully."}
