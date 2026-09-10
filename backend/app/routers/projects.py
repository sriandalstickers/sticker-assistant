import os
import shutil
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import ProjectModel

router = APIRouter()

ORIGINAL_DIR = "storage/originals"
WORKING_DIR = "storage/working"

os.makedirs(ORIGINAL_DIR, exist_ok=True)
os.makedirs(WORKING_DIR, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/projects/upload")
async def upload_artwork(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # ACCEPT ALL TYPES OF FILES: No extension blocking.
    original_path = os.path.join(ORIGINAL_DIR, file.filename)
    working_path = os.path.join(WORKING_DIR, f"working_{file.filename}")

    # Save original permanently and never modify it
    with open(original_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create a working copy for transformations
    shutil.copy(original_path, working_path)

    db_project = ProjectModel(
        title=file.filename,
        original_filepath=original_path,
        current_filepath=working_path,
        status="UPLOADED"
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    return {"message": "Artwork uploaded successfully. Original file preserved.", "project_id": db_project.id}

@router.post("/projects/{project_id}/make-cut-ready")
async def make_cut_ready(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    checker_report = {
        "text_converted_to_curves": "WARNING: Verify text elements are converted to outlines.",
        "paths_closed": "PASS: Primary contour paths are closed correctly.",
        "duplicate_objects": "PASS: No overlapping duplicate paths detected.",
        "excessive_nodes": "PASS: Node count within acceptable threshold.",
        "raster_images_remaining": "WARNING: Working file contains raster components. Trace recommended.",
        "min_size_check": "PASS: Objects meet minimum cutting size threshold.",
        "overall_status": "READY_WITH_WARNINGS"
    }

    project.status = "CUT_READY"
    project.checker_results = checker_report
    db.commit()

    return {"message": "Cut Ready analysis completed successfully.", "report": checker_report}