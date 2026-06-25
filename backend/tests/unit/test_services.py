import asyncio
import datetime
import logging
import uuid
from typing import Any, Callable

import boto3

from app.core.config import settings
from app.dto.image import ProcessingStatus
from app.repository.dynamo_image_repo import DynamoImageRepository
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)
endpoint_url = settings.LOCALSTACK_ENDPOINT or None


class ImageService:

    @classmethod
    def _get_s3_client(cls):
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=settings.AWS_REGION,
        )

    @classmethod
    async def _run_in_executor(cls, func: Callable, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    # -----------------------
    # REQUEST UPLOAD URL
    # -----------------------
    @staticmethod
    async def get_upload_url(repo: DynamoImageRepository, filename: str, content_type: str, user: dict):
        image_id = str(uuid.uuid4())
        s3_key = f"raw/{image_id}-{filename}"
        now = datetime.datetime.utcnow().isoformat()

        await repo.create({
            "id": image_id,
            "filename": filename,
            "status": ProcessingStatus.PENDING.value.upper(),
            "s3_key": s3_key,
            "created_at": now,
            "created_by": user["sub"],
            "created_by_email": user.get("email"),
        })

        presigned_url = S3Service().generate_presigned_url(
            object_name=s3_key,
            content_type=content_type,
        )

        return {"image_id": image_id, "upload_url": presigned_url}

    # -----------------------
    # ALREADY PROCESSED?
    # -----------------------
    @staticmethod
    async def already_processed(repo: DynamoImageRepository, key: str) -> bool:
        resp = await repo.list_by_status(ProcessingStatus.COMPLETED.value.upper())
        return any(item.get("s3_key") == key for item in resp["items"])

    # -----------------------
    # PROCESS IMAGE
    # -----------------------
    @classmethod
    async def process_image(cls, repo: DynamoImageRepository, bucket: str, key: str) -> str:
        s3 = cls._get_s3_client()
        new_key = f"processed/{key.split('/')[-1]}"

        all_items = await repo.list_all()
        image_record = next((i for i in all_items if i.get("s3_key") == key), None)

        if not image_record:
            logger.error("Record not found for key: %s", key)
            raise ValueError(f"Record not found for key: {key}")

        await cls._run_in_executor(
            s3.copy_object,
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": key},
            Key=new_key,
        )

        try:
            await cls._run_in_executor(s3.delete_object, Bucket=bucket, Key=key)
        except Exception:
            logger.warning("Failed to delete %s", key, exc_info=True)

        return new_key

    # -----------------------
    # GET ALL IMAGES (FIXED)
    # -----------------------
    @classmethod
    async def get_all_images(cls, repo: DynamoImageRepository, user_id: str | None = None):

        if user_id:
            items = await repo.list_by_user(user_id)
        else:
            items = await repo.list_all()

        s3 = S3Service()

        return [
            {
                "id": item["id"],
                "filename": item["filename"],
                "status": item["status"].lower(),
                "s3_key": s3.generate_presigned_url(
                    object_name=item["s3_key"],
                    method="get_object",
                    expiration=900,
                ),
                "url": s3.generate_presigned_url(
                    object_name=item.get("s3_processed_file") or item["s3_key"],
                    method="get_object",
                ),
                "created_at": item["created_at"],
            }
            for item in items
        ]

    # -----------------------
    # ADMIN STATS (NEW API SUPPORT)
    # -----------------------
    @staticmethod
    async def get_admin_stats(repo: DynamoImageRepository):
        import anyio

        def scan_images():
            return repo.dynamo.table.scan()

        resp = await anyio.to_thread.run_sync(scan_images)
        items = resp.get("Items", [])

        users = {i.get("created_by") for i in items if i.get("created_by")}

        return {
            "total_users": len(users),
            "total_files": len(items),
        }