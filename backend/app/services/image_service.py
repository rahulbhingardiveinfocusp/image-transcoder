import asyncio
import logging
from typing import Any, Callable
from urllib.parse import unquote

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.image import Image, ProcessingStatus
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

    @staticmethod
    async def get_upload_url(db: AsyncSession, filename: str, content_type: str):
        new_image = Image(filename=filename, s3_key="")
        try:
            db.add(new_image)
            await db.flush()
            new_image.s3_key = f"raw/{new_image.id}-{filename}"
            await db.commit()
            await db.refresh(new_image)
        except Exception:
            await db.rollback()
            raise

        presigned_url = S3Service().generate_presigned_url(
            object_name=new_image.s3_key,
            content_type=content_type,
        )
        return {"image_id": new_image.id, "upload_url": presigned_url}

    @staticmethod
    async def already_processed(session: AsyncSession, bucket: str, key: str) -> bool:
        result = await session.execute(
            select(Image).where(
                Image.s3_key == key,
                Image.status == ProcessingStatus.COMPLETED,
            )
        )
        return result.scalar_one_or_none() is not None

    @classmethod  
    async def process_image(cls, session: AsyncSession, bucket: str, key: str) -> str:

        s3 = cls._get_s3_client()
        new_key = f"processed/{key.split('/')[-1]}"

        result = await session.execute(select(Image).where(Image.s3_key == key))
        image_record = result.scalars().first()
        if not image_record:
            logger.error("Record not found for key: %s", key)
            raise ValueError(f"Record not found for key: {key}")

        try:
            await cls._run_in_executor(
                s3.copy_object,
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": key},
                Key=new_key,
            )
        except Exception:
            logger.exception("S3 copy failed for %s", key)
            raise  # let the caller handle status transitions

        try:
            await cls._run_in_executor(s3.delete_object, Bucket=bucket, Key=key)
        except Exception:
            logger.warning("Failed to delete original %s (non-fatal)", key, exc_info=True)

        return new_key
    
    @classmethod
    async def download_image(cls, bucket: str, key: str) -> bytes:
        s3 = cls._get_s3_client()
        def _get_and_read():
            return s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        return await cls._run_in_executor(_get_and_read)

    @classmethod
    async def upload_thumbnail(cls, bucket: str, key: str, data: bytes) -> None:
        s3 = cls._get_s3_client()
        await cls._run_in_executor(s3.put_object, Bucket=bucket, Key=key, Body=data)
        

    @classmethod
    async def get_all_images(cls, db: AsyncSession):
        result = await db.execute(
            select(Image).order_by(Image.created_at.desc())
        )
        images = result.scalars().all()

        s3 = S3Service()
        logger.info("all imgs: %s", images)
        return [
            {
                "id": str(image.id),
                "filename": image.filename,
                "status": image.status.value,
                "url": s3.generate_presigned_url(
                    object_name=image.s3_processed_file or image.s3_key, 
                    method="get_object"
                ),

                "created_at": image.created_at,
            }
            for image in images
        ]