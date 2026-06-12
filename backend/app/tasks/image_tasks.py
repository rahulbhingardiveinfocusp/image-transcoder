import asyncio
import logging
import urllib.parse
from io import BytesIO
from PIL import Image as PILImage

from app.tasks.celery_app import celery_app
from app.services.image_service import ImageService
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True, 
    max_retries=3, 
    default_retry_delay=60, 
    queue="image-processing-queue"
)
def process_s3_upload_task(self, bucket: str, key: str):
    """
    Celery task entrypoint for processing S3 image uploads.
    Runs async pipeline safely inside a dedicated event loop context.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(run_processing_logic(bucket, key))

    except Exception as exc:
        logger.exception(f"Task processing failure for s3://{bucket}/{key}")
        raise self.retry(exc=exc)

    finally:
        loop.close()


async def run_processing_logic(bucket: str, key: str):
    """
    Async pipeline:
    1. Parse URL encoded characters safely
    2. Guard against double-processing via database state check
    3. Download source from S3
    4. Offload CPU-heavy thumbnail rendering to separate thread
    5. Save thumbnail to destination folder
    6. Transfer/rename original image object state
    """
    # Fix S3 URL space/special characters encoding (e.g., 'raw/my+photo.jpg' -> 'raw/my photo.jpg')
    key = urllib.parse.unquote_plus(key)

    # -------------------------------------------------
    # Idempotency guard
    # -------------------------------------------------
    if hasattr(ImageService, "already_processed"):
        if await ImageService.already_processed(bucket, key):
            logger.info(f"[-] Bypassing execution. Image already marked completed: {key}")
            return {"status": "already_processed"}

    # -------------------------------------------------
    # 1. Download image object data
    # -------------------------------------------------
    image_data = await ImageService.download_image(bucket, key)

    # -------------------------------------------------
    # 2. Generate thumbnail (CPU-bound workflow offloaded to worker thread)
    # -------------------------------------------------
    thumbnail_data = await asyncio.to_thread(_generate_thumbnail, image_data)

    # -------------------------------------------------
    # 3. Upload generated thumbnail
    # -------------------------------------------------
    filename = key.split('/')[-1]
    thumbnail_key = f"thumbnails/{filename}"
    await ImageService.upload_thumbnail(bucket, thumbnail_key, thumbnail_data)

    # -------------------------------------------------
    # 4. Relocate / register original image state
    # -------------------------------------------------
    success = await ImageService.process_image(bucket, key)

    if not success:
        raise RuntimeError(f"Failed to finalise image processing state for {bucket}/{key}")

    logger.info(f"[+] Task successful for s3://{bucket}/{key} -> Thumbnail: {thumbnail_key}")

    return {
        "status": "success",
        "bucket": bucket,
        "key": key,
        "thumbnail": thumbnail_key,
    }


def _generate_thumbnail(data: bytes) -> bytes:
    """
    CPU-bound image reduction routine.
    """
    with PILImage.open(BytesIO(data)) as im:
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")

        im.thumbnail((128, 128))

        buffer = BytesIO()
        im.save(buffer, format="JPEG")

        return buffer.getvalue()