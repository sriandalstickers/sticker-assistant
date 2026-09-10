import cv2
import numpy as np
import os
from fastapi import APIRouter, HTTPException, Path
from ..database import get_db # adjust imports as per your project layout

router = APIRouter()

@router.post("/projects/{project_id}/trace")
def trace_raster_to_vector(project_id: int):
    # 1. Locate your stored original image path from your database/storage logic
    # (Assuming you have a way to fetch the image path for this project_id)
    # Example path lookup:
    input_path = f"storage/uploads/{project_id}_original.png" # Adjust to match your file naming convention
    
    if not os.path.exists(input_path):
        # Fallback search or handle error if file path varies
        # Let's make sure it handles grayscale/binary reading properly
        pass

    # Read the image in grayscale
    img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=404, detail="Original image not found for tracing.")

    # Step 2: Apply thresholding to get a clean black-and-white binary image
    _, thresh = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)

    # Step 3: Apply a slight Gaussian blur to smooth out pixel stair-steps/jaggies
    blurred = cv2.GaussianBlur(thresh, (5, 5), 0)

    # Step 4: Find contours on the smoothed image
    contours, _ = cv2.findContours(blurred, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    smoothed_contours = []
    svg_paths = []

    for cnt in contours:
        # Filter out tiny speckles/noise based on area
        if cv2.contourArea(cnt) < 15.0:
            continue

        # Step 5: Douglas-Peucker Polygon Approximation for smooth curves
        # epsilon controls the smoothness: higher value = smoother curves, lower value = more detail
        epsilon = 0.002 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        
        smoothed_contours.append(approx)

        # Build clean SVG path string from smoothed points
        if len(approx) > 0:
            path_data = f"M {approx[0][0][0]} {approx[0][0][1]}"
            for point in approx[1:]:
                path_data += f" L {point[0][0]} {point[0][1]}"
            path_data += " Z"
            svg_paths.append(path_data)

    # Step 6: Generate final clean SVG markup
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {img.shape[1]} {img.shape[0]}">
  <path d="{" ".join(svg_paths)}" fill="black" stroke="none" />
</svg>'''

    # Save the generated SVG output path
    output_svg_path = f"storage/outputs/{project_id}_clean.svg"
    os.makedirs(os.path.dirname(output_svg_path), exist_ok=True)
    with open(output_svg_path, "w") as f:
        f.write(svg_content)

    return {
        "message": "Vector successfully smoothed and generated!",
        "contours_traced": len(smoothed_contours),
        "svg_file": output_svg_path
    } 