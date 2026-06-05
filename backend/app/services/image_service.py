import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.models.image import Image
from app.services.email_service import EmailService
from app.services.s3_service import S3Service
import io
import boto3
import logging
from PIL import Image as PILImage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.image import Image
import io
import boto3
from urllib.parse import unquote
from PIL import Image as PILImage
from app.models.image import Image
from app.services.s3_service import S3Service
from app.services.email_service import EmailService
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageService:
    @staticmethod
    async def get_upload_url(db: AsyncSession, filename: str):
        # 1. Create DB record
        new_image = Image(filename=filename, s3_key=f"raw/{filename}")
        db.add(new_image)
        await db.commit()
        await db.refresh(new_image)
        
        # 2. Generate S3 URL
        s3_service = S3Service()
        presigned_url = s3_service.generate_presigned_url(f"raw/{filename}")
        
        return {"image_id": new_image.id, "upload_url": presigned_url}
    

    @staticmethod
    async def process_image(bucket: str, key: str):
        decoded_key = unquote(key)
        new_key = f"processed/{decoded_key.split('/')[-1]}"
        
        # 1. Use ASYNC WITH for AsyncSession
        async with AsyncSessionLocal() as db:
            
            # 2. Use await and select() instead of db.query()
            result = await db.execute(select(Image).filter(Image.s3_key == decoded_key))
            image_record = result.scalars().first()
            
            if not image_record:
                print(f"Record not found: {decoded_key}")
                return False
                
            # 3. Perform S3 Move (Note: boto3 is synchronous, which blocks the event loop, 
            # but it will function. For a true async app, look into aioboto3 later).
            s3 = boto3.client(
                "s3", endpoint_url="http://localstack:4566",
                aws_access_key_id="test", aws_secret_access_key="test", region_name="us-east-1"
            )
            
            try:
                s3.copy_object(
                    Bucket=bucket, 
                    CopySource={'Bucket': bucket, 'Key': decoded_key}, 
                    Key=new_key
                )
                s3.delete_object(Bucket=bucket, Key=decoded_key)
                
                # 4. Update Database and AWAIT the commit
                image_record.s3_key = new_key
                image_record.status = "COMPLETED"
                await db.commit()  # <-- Added await
                
                print(f"Successfully moved {decoded_key} to {new_key}")
                return True
                
            except Exception as e:
                await db.rollback()  # <-- Added await
                print(f"Error moving file: {e}")
                return False
    @staticmethod
    def _get_s3_client():
        # Centralized client creation to avoid repetition and ensure localstack connectivity
        return boto3.client(
            "s3", 
            endpoint_url="http://localstack:4566",
            aws_access_key_id="test", 
            aws_secret_access_key="test", 
            region_name="us-east-1"
        )

    @staticmethod
    async def download_image(bucket: str, key: str) -> bytes:
        # Running sync boto3 in an executor prevents blocking the event loop
        loop = asyncio.get_event_loop()
        s3 = ImageService._get_s3_client()
        
        def _download():
            response = s3.get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
            
        return await loop.run_in_executor(None, _download)

    @staticmethod
    async def upload_thumbnail(bucket: str, key: str, data: bytes):
        loop = asyncio.get_event_loop()
        s3 = ImageService._get_s3_client()
        
        def _upload():
            s3.put_object(Bucket=bucket, Key=key, Body=data)
            
        await loop.run_in_executor(None, _upload)