from app.services.cognito import require_admin, verify_cognito_token
from fastapi import APIRouter, Depends

from app.deps import get_image_repo
from app.dto.image import ImageResponse, UploadRequest
from app.repository.dynamo_image_repo import DynamoImageRepository
from app.services.image_service import ImageService

router = APIRouter()


@router.post("/request-upload")
async def request_upload(
    payload: UploadRequest,
    user: dict = Depends(verify_cognito_token),
    repo: DynamoImageRepository = Depends(get_image_repo),
):
    return await ImageService.get_upload_url(
        repo,
        payload.filename,
        payload.content_type,
        user,
    )

@router.get("/get-all-images", response_model=list[ImageResponse])
async def get_all_images(
    user: dict = Depends(verify_cognito_token),
    repo: DynamoImageRepository = Depends(get_image_repo),
):
    return await ImageService.get_all_images(
        repo,
        user["sub"],
    )

@router.get(
    "/admin/users/{user_id}/files",
    response_model=list[ImageResponse]
)
async def get_user_files(
    user_id: str,
    admin: dict = Depends(require_admin),
    repo: DynamoImageRepository = Depends(get_image_repo),
):
    return await ImageService.get_user_images(
        repo,
        user_id
    )

@router.get("/admin/stats")
async def get_admin_stats(
    admin: dict = Depends(require_admin),
    repo: DynamoImageRepository = Depends(get_image_repo),
):
    return await ImageService.get_admin_stats(repo)