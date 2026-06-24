from fastapi import APIRouter, Depends

from app.deps import get_image_repo
from app.dto.image import ImageResponse, UploadRequest
from app.repository.dynamo_image_repo import DynamoImageRepository
from app.services.image_service import ImageService

router = APIRouter()


@router.post("/request-upload")
async def request_upload(
    payload: UploadRequest,
    repo: DynamoImageRepository = Depends(get_image_repo),   # FIX: was AsyncSession
):
    return await ImageService.get_upload_url(repo, payload.filename, payload.content_type)


@router.get("/get-all-images", response_model=list[ImageResponse])
async def get_all_images(
    repo: DynamoImageRepository = Depends(get_image_repo),   # FIX: was AsyncSession
):
    return await ImageService.get_all_images(repo)