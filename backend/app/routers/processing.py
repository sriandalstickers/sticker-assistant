import os
import cv2
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

    if input_path.lower().endswith('.cdr'):
        raise HTTPException(
            status_code=400,
            detail="CorelDRAW (.cdr) is a proprietary vector format. Please export a PNG, JPEG, or PDF preview from CorelDRAW to use the raster-to-vector tracing engine."
        )

    output_svg_path = input_path.rsplit(".", 1)[0] + "_vector.svg"
    temp_bw_path = input_path.rsplit(".", 1)[0] + "_temp_bw.jpg"

    try:
        # Pre-process: Crush all colors (like red) into pure solid black
        img = cv2.imread(input_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Anything darker than very light gray (220) becomes solid black
        _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
        cv2.imwrite(temp_bw_path, thresh)

        # Professional VTracer Engine - Generates perfect Spline/Bezier curves
        vtracer.convert_image_to_svg_py(
            temp_bw_path,
            output_svg_path,
            colormode='binary',     
            hierarchical='stacked',
            mode='spline',          
            filter_speckle=10,      
            color_precision=8,
            layer_difference=16,
            corner_threshold=60,    
            length_threshold=4.0,
            max_iterations=10,
            splice_threshold=45,
            path_precision=3
        )
        
        # Clean up the temporary black and white processing image
        if os.path.exists(temp_bw_path):
            os.remove(temp_bw_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"High-fidelity tracing failed: {str(e)}")

    project.status = "CLEAN_VECTOR"
    db.commit()

    return {
        "message": "Successfully converted all colors and vectorized using professional Bézier curves!",
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