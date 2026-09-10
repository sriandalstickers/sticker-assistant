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

    # 1. SMART BYPASS: Skip already-vector files
    if ext in vector_formats:
        dwg = svgwrite.Drawing(output_svg_path, profile='tiny', size=("800px", "600px"))
        dwg.add(dwg.text(f"File uploaded is a .{ext.upper()} vector format.", insert=(50, 100), fill="black", font_size="24px"))
        dwg.add(dwg.text("Raster-to-vector tracing is not required.", insert=(50, 150), fill="black", font_size="18px"))
        dwg.add(dwg.text("Please use the downloaded original file directly.", insert=(50, 200), fill="black", font_size="18px"))
        dwg.save()

        project.status = "CLEAN_VECTOR"
        db.commit()

        return {
            "message": f"Detected .{ext.upper()} file. Bypassed tracing since it is already a vector format.",
            "vector_file": output_svg_path
        }

    try:
        # 2. UNIVERSAL IMAGE LOADER
        img = cv2.imread(input_path)
        if img is None:
            pil_img = Image.open(input_path).convert('RGB')
            img = np.array(pil_img)
            img = img[:, :, ::-1].copy()

        # 3. SMART SCALING (Fixes the 502 Bad Gateway Crash)
        # Scales the longest edge to exactly 1800px. High enough for smooth cuts, safe for 512MB RAM.
        h, w = img.shape[:2]
        target_max = 1800.0
        scale = target_max / max(h, w)
        
        if scale > 1:
            img_working = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        else:
            img_working = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        
        # 4. Convert to Grayscale & Blur for smooth geometry
        gray = cv2.cvtColor(img_working, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 5. Threshold to solid black and white
        _, thresh = cv2.threshold(blur, 200, 255, cv2.THRESH_BINARY)
        
        # 6. Morphological ironing
        kernel = np.ones((3, 3), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        cv2.imwrite(temp_bw_path, thresh)

        # 7. VTracer Engine
        vtracer.convert_image_to_svg_py(
            temp_bw_path,
            output_svg_path,
            colormode='binary',     
            hierarchical='stacked',
            mode='spline',          
            filter_speckle=20,      
            color_precision=8,
            layer_difference=16,
            corner_threshold=45,    
            length_threshold=10.0,  
            max_iterations=10,
            splice_threshold=45,
            path_precision=3
        )
        
        if os.path.exists(temp_bw_path):
            os.remove(temp_bw_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tracing failed: {str(e)}")

    project.status = "CLEAN_VECTOR"
    db.commit()

    return {
        "message": "Successfully applied smart smoothing and vectorized for plotter cutting!",
        "vector_file": output_svg_path
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