from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import projects, processing

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sticker & Vinyl Cutting Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api", tags=["Projects"])
app.include_router(processing.router, prefix="/api", tags=["Processing"])

@app.get("/")
def read_root():
    return {"message": "Sticker & Vinyl Cutting Assistant Backend is running successfully!"}