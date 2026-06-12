import asyncio
import logging
from urllib.parse import unquote
import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.image import Image
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)
endpoint_url = settings.LOCALSTACK_ENDPOINT or None
class ImageService:
    @classmethod
    def _get_s3_client(cls):
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=settings.AWS_REGION
        )

    @staticmethod
    async def _run_in_executor(func, *args):
        """Helper to run blocking sync functions without blocking the loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args)

    @staticmethod
    async def get_upload_url(db: AsyncSession, filename: str, content_type:str):
        new_image = Image(
            filename=filename,
            s3_key=f"raw/{filename}"
        )

        db.add(new_image)
        await db.commit()
        await db.refresh(new_image)

        s3_service = S3Service()

        presigned_url = s3_service.generate_presigned_url(
            object_name=f"raw/{filename}",
            content_type=content_type
        )

        return {
            "image_id": new_image.id,
            "upload_url": presigned_url
        }

    @classmethod
    async def process_image(cls, bucket: str, key: str):
        decoded_key = unquote(key)
        new_key = f"processed/{decoded_key.split('/')[-1]}"
        s3 = cls._get_s3_client()

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Image).filter(Image.s3_key == decoded_key))
            image_record = result.scalars().first()
            
            if not image_record:
                logger.error(f"Record not found: {decoded_key}")
                return False
                
            try:
                # Wrap blocking S3 calls in executor
                await cls._run_in_executor(s3.copy_object, {
                    'Bucket': bucket, 'CopySource': {'Bucket': bucket, 'Key': decoded_key}, 'Key': new_key
                })
                await cls._run_in_executor(s3.delete_object, {'Bucket': bucket, 'Key': decoded_key})
                
                image_record.s3_key = new_key
                image_record.status = "COMPLETED"
                await db.commit()
                return True
            except Exception as e:
                await db.rollback()
                logger.exception(f"Error moving file: {e}")
                return False

    @classmethod
    async def download_image(cls, bucket: str, key: str) -> bytes:
        s3 = cls._get_s3_client()
        def _download():
            return s3.get_object(Bucket=bucket, Key=key)['Body'].read()
        return await cls._run_in_executor(_download)

    @classmethod
    async def upload_thumbnail(cls, bucket: str, key: str, data: bytes):
        s3 = cls._get_s3_client()
        await cls._run_in_executor(s3.put_object, Bucket=bucket, Key=key, Body=data)