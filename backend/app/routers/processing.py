import os
import cv2
import numpy as np
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import ProjectModel
import svgwrite
import vtracer

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
    output_svg_path = input_path.rsplit(".", 1)[0] + "_vector.svg"
    temp_bw_path = input_path.rsplit(".", 1)[0] + "_temp_bw.jpg"
    
    ext = input_path.lower().split('.')[-1]
    vector_formats = ['cdr', 'pdf', 'ai', 'eps', 'svg']

    if ext in vector_formats:
        dwg = svgwrite.Drawing(output_svg_path, profile='tiny', size=("800px", "600px"))
        dwg.add(dwg.text(f"File uploaded is a .{ext.upper()} vector format.", insert=(50, 100), fill="black", font_size="24px"))
        dwg.save()
        project.status = "CLEAN_VECTOR"
        db.commit()
        return {"message": "Bypassed vector tracing.", "vector_file": output_svg_path}

    try:
        # 1. Universal Image Loader
        img = cv2.imread(input_path)
        if img is None:
            pil_img = Image.open(input_path).convert('RGB')
            img = np.array(pil_img)
            img = img[:, :, ::-1].copy()

        # 2. High-Resolution Scaling for Blade Precision
        h, w = img.shape[:2]
        target_max = 2400.0
        scale = target_max / max(h, w)
        
        if scale > 1:
            img_working = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
        else:
            img_working = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        
        # 3. Grayscale & Adaptive Thresholding
        gray = cv2.cvtColor(img_working, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 4. Auto-Invert Background for Plotter Safety
        corners = [int(thresh[0,0]), int(thresh[0,-1]), int(thresh[-1,0]), int(thresh[-1,-1])]
        if sum(corners) < 510:
            thresh = cv2.bitwise_not(thresh)
            
        cv2.imwrite(temp_bw_path, thresh)

        # 5. Ultra-Clean VTracer Engine (Optimized to eliminate jagged node clusters)
        vtracer.convert_image_to_svg_py(
            temp_bw_path,
            output_svg_path,
            colormode='binary',     
            hierarchical='stacked',
            mode='spline',          
            filter_speckle=6,       
            color_precision=8,
            layer_difference=16,
            corner_threshold=70,    # High corner threshold locks straight edges flat
            length_threshold=5.0,   # Eliminates microscopic line fragments that break blades
            max_iterations=12,
            splice_threshold=50,
            path_precision=6
        )
        
        if os.path.exists(temp_bw_path):
            os.remove(temp_bw_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tracing failed: {str(e)}")

    project.status = "CLEAN_VECTOR"
    db.commit()

    return {
        "message": "Successfully generated blade-safe ultra-precise vector curves!",
        "vector_file": output_svg_path
    }

@router.post("/projects/{project_id}/add-text")
async def add_vector_text(project_id: int, request: TextRequest, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    output_svg_path = project.current_filepath.rsplit(".", 1)[0] + "_vector.svg"

    dwg = svgwrite.Drawing(output_svg_path, profile='tiny', size=("800px", "600px"))
    dwg.add(dwg.text(request.text, insert=(50, 150), font_size=f"{request.font_size}px", font_family="Arial", font_weight="bold", fill="black"))
    dwg.save()

    project.status = "CLEAN_VECTOR"
    db.commit()

    return {"message": "Text vector generated", "vector_file": output_svg_path}

@router.get("/projects/{project_id}/export/svg")
async def export_svg(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    
    vector_path = project.current_filepath.rsplit(".", 1)[0] + "_vector.svg"
    return FileResponse(vector_path, media_type="image/svg+xml", filename=f"sticker_{project.id}_cut_ready.svg")

@router.get("/projects/{project_id}/export/cdr-guide")
async def export_cdr_guide(project_id: int, db: Session = Depends(get_db)):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_no=404, detail="Project not found.")
    vector_path = project.current_filepath.rsplit(".", 1)[0] + "_vector.svg"
    
    return {
        "format": "CorelDRAW (.CDR) Production Workflow",
        "notice": "Import SVG directly into CorelDRAW and Ungroup (Ctrl+U) for cutting.",
        "svg_source": vector_path
    }