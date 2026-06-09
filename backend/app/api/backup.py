"""Backup and restore API endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app.config import settings
from app.services.backup_service import BackupService

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.get("/export")
def export_data(db: Session = Depends(get_db)):
    """Export all data as a downloadable JSON file."""
    try:
        data = BackupService.export_data(db)
        return JSONResponse(
            content=data,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="invoice_backup_{data["export_date"][:10]}.json"'
                )
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_data(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import data from a JSON backup file. Replaces all existing data."""
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        counts = BackupService.import_data(db, data)
        return {
            "message": "Data imported successfully",
            "counts": counts,
        }
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
def list_backups():
    """List all available auto-backup files."""
    return BackupService.list_backups()


@router.post("/create")
def create_backup():
    """Manually trigger a database backup."""
    backup_name = BackupService.create_auto_backup()
    if backup_name:
        return {"message": "Backup created successfully", "filename": backup_name}
    raise HTTPException(status_code=500, detail="Failed to create backup.")


@router.get("/download/{filename}")
def download_backup(filename: str):
    """Download a specific backup file."""
    backup_path = Path(settings.BACKUP_DIR) / filename
    if not backup_path.exists() or not filename.startswith("backup_"):
        raise HTTPException(status_code=404, detail="Backup not found.")
    return FileResponse(
        str(backup_path),
        filename=filename,
        media_type="application/octet-stream",
    )
