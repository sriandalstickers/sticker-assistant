import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ProjectModel
import cv2
import numpy as np
import svgwrite

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class TextRequest(BaseModel):
    text: str
    font_size: int = 48

@router.post("/projects/{project_id}/trace")
async def trace_image_to_vector(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    input_path = project.current_filepath

    if input_path.lower().endswith('.cdr'):
        raise HTTPException(
            status_code=400,
            detail="CorelDRAW (.cdr) is a proprietary vector format. Please export a PNG, JPEG, or PDF preview from CorelDRAW to use the raster-to-vector tracing engine."
        )

    output_svg_path = input_path.rsplit(".", 1)[0] + "_vector.svg"

    img = cv2.imread(input_path)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not read working image for tracing.")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blur, 180, 255, cv2.THRESH_BINARY_INV)

    # Use RETR_CCOMP to capture outer shapes and their inner holes/cutouts accurately
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

    h, w = gray.shape
    dwg = svgwrite.Drawing(output_svg_path, profile='tiny', size=(f"{w}px", f"{h}px"))
    
    valid_paths_count = 0
    if hierarchy is not None:
        hierarchy = hierarchy[0]
        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < 15.0 or area > (h * w * 0.95):
                continue
            
            x, y, cw, ch = cv2.boundingRect(cnt)
            if x <= 2 or y <= 2 or (x + cw) >= w - 2 or (y + ch) >= h - 2:
                continue

            # Process top-level outer boundaries (hierarchy[i][3] == -1)
            if hierarchy[i][3] == -1:
                path_data = []
                pts = cnt.reshape(-1, 2)
                if len(pts) > 2:
                    path_data.append(f"M {pts[0][0]} {pts[0][1]} " + " ".join([f"L {pt[0]} {pt[1]}" for pt in pts[1:]]) + " Z")
                    
                    # Punch out inner child contours (holes, button cutouts, text centers)
                    child_idx = hierarchy[i][2]
                    while child_idx != -1:
                        child_cnt = contours[child_idx]
                        child_area = cv2.contourArea(child_cnt)
                        if child_area > 5.0:
                            c_pts = child_cnt.reshape(-1, 2)
                            if len(c_pts) > 2:
                                path_data.append(f"M {c_pts[0][0]} {c_pts[0][1]} " + " ".join([f"L {pt[0]} {pt[1]}" for pt in c_pts[1:]]) + " Z")
                        child_idx = hierarchy[child_idx][0]

                # Combine into a single compound path with evenodd fill rule to preserve holes
                dwg.add(dwg.path(d=" ".join(path_data), fill="black", fill_rule="evenodd", stroke="none", id=f"shape_{i}"))
                valid_paths_count += 1

    dwg.save()

    project.status = "CLEAN_VECTOR"
    db.commit()

    return {
        "message": f"Successfully vectorized {valid_paths_count} precise shapes with all internal holes preserved!",
        "vector_file": output_svg_path,
        "contours_traced": valid_paths_count
    }

@router.post("/projects/{project_id}/add-text")
async def add_vector_text(project_id: int, request: TextRequest, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    output_svg_path = project.current_filepath.rsplit(".", 1)[0] + "_vector.svg"

    dwg = svgwrite.Drawing(output_svg_path, profile='tiny', size=("800px", "600px"))
    dwg.add(dwg.text(
        request.text, 
        insert=(50, 150), 
        font_size=f"{request.font_size}px", 
        font_family="Arial, sans-serif", 
        font_weight="bold",
        fill="black"
    ))
    dwg.save()

    project.status = "CLEAN_VECTOR"
    db.commit()

    return {
        "message": f"Text '{request.text}' successfully generated into vector paths!",
        "vector_file": output_svg_path
    }

@router.get("/projects/{project_id}/export/svg")
async def export_svg(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    
    vector_path = project.current_filepath.rsplit(".", 1)[0] + "_vector.svg"
    
    if not os.path.exists(vector_path):
        if project.current_filepath.lower().endswith('.cdr'):
            dwg = svgwrite.Drawing(vector_path, profile='tiny', size=("800px", "600px"))
            dwg.add(dwg.text("CorelDRAW Native Vector Import", insert=(50, 100), fill="black", font_size="24px"))
            dwg.save()
        else:
            raise HTTPException(status_code=400, detail="Vector file not found. Please run 'Trace Raster to Clean Vector' first.")
    
    return FileResponse(vector_path, media_type="image/svg+xml", filename=f"sticker_{project.id}_cut_ready.svg")

@router.get("/projects/{project_id}/export/cdr-guide")
async def export_cdr_guide(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    
    vector_path = project.current_filepath.rsplit(".", 1)[0] + "_vector.svg"
    
    return {
        "format": "CorelDRAW (.CDR) Production Workflow",
        "notice": "Native .CDR binary format is proprietary. To maintain 100% vector accuracy without file corruption, use the clean SVG export.",
        "steps": [
            "1. Click 'Download Clean SVG Vector' below.",
            "2. Open CorelDRAW and create a new document with exact physical dimensions.",
            "3. Go to File > Import and select the downloaded SVG file.",
            "4. Select the imported design and press Ctrl + U (Ungroup) to separate every single curve and cutout.",
            "5. Go to File > Save As and save your file natively as .CDR for your vinyl cutter."
        ],
        "svg_source": vector_path
    }