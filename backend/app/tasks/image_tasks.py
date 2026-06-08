import asyncio
import logging
from io import BytesIO
from PIL import Image as PILImage
from app.tasks.celery_app import celery_app
from app.services.image_service import ImageService
from app.services.email_service import EmailService # Added import
from app.core.config import settings

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_s3_upload_task(self, bucket: str, key: str):
    try:
        return asyncio.run(run_processing_logic(bucket, key))
    except Exception as exc:
        logger.error(f"Task failed for {key}: {exc}")
        raise self.retry(exc=exc)

async def run_processing_logic(bucket: str, key: str):
    if key.startswith("processed/"):
        return {"status": "skipped"}
    
    # 1. Download
    image_data = await ImageService.download_image(bucket, key)
    
    # 2. Thumbnail Processing
    thumbnail_data = _generate_thumbnail(image_data)
    
    # 3. Upload & Move
    thumbnail_key = f"thumbnails/{key.split('/')[-1]}"
    await ImageService.upload_thumbnail(bucket, thumbnail_key, thumbnail_data)
    
    success = await ImageService.process_image(bucket, key)
    if not success:
        raise RuntimeError(f"Failed to process image move for {key}")

    # 4. Notify Admin
    # Assuming EmailService.send_image_links expects a list of links/keys
    # await EmailService.send_image_links(
    #     settings.ADMIN_EMAIL, 
    #     [f"Original: {key}", f"Thumbnail: {thumbnail_key}"]
    # )
    logger.info(f"Notification sent to {settings.ADMIN_EMAIL}")
        
    return {"status": "success", "key": key}

def _generate_thumbnail(data: bytes) -> bytes:
    """Synchronous CPU-bound image processing."""
    with PILImage.open(BytesIO(data)) as im:
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        im.thumbnail((128, 128))
        buffer = BytesIO()
        im.save(buffer, format="JPEG")
        return buffer.getvalue()