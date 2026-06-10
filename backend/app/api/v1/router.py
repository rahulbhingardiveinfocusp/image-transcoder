# app/api/v1/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.image_service import ImageService
from pydantic import BaseModel

router = APIRouter()

class UploadRequest(BaseModel):
    filename: str
    content_type: str

@router.post("/request-upload")
async def request_upload(payload: UploadRequest, db: AsyncSession = Depends(get_db)):
    result = await ImageService.get_upload_url(db, payload.filename,payload.content_type)
    return result