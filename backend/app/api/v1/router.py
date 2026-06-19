from app.dto.Image_dto import ImageResponse, UploadRequest
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.image_service import ImageService
from pydantic import BaseModel

router = APIRouter()
 
@router.post("/request-upload")
async def request_upload(payload: UploadRequest, db: AsyncSession = Depends(get_db)):
    result = await ImageService.get_upload_url(db, payload.filename, payload.content_type)
    return result

@router.get("/get-all-images", response_model=list[ImageResponse],)
async def get_all_images(db: AsyncSession = Depends(get_db)):
    return await ImageService.get_all_images(db)