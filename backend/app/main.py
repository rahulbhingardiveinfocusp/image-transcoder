from fastapi import Depends, FastAPI
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.services.image_service import ImageService
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware
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

class UploadRequest(BaseModel):
    filename: str
@app.post("/images/request-upload")
async def request_upload(payload: UploadRequest, db: AsyncSession = Depends(get_db)):
    result = await ImageService.get_upload_url(db, payload.filename)
    return result