from fastapi import Depends, FastAPI
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.services.image_service import ImageService
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import router as v1_router
app = FastAPI(title=settings.PROJECT_NAME)
origins = [
    "http://localhost:4200", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, etc.)
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def root():
    return {"message": "Image Transcoding Service is operational"}

app.include_router(v1_router, prefix="/images/request-upload", tags=["images"])