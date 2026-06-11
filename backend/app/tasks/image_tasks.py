import asyncio
import logging
from io import BytesIO
from PIL import Image as PILImage

from app.tasks.celery_app import celery_app
from app.services.image_service import ImageService
from app.services.email_service import EmailService
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_s3_upload_task(self, bucket: str, key: str):
    """
    Celery task entrypoint for processing S3 image uploads.
    Runs async pipeline safely inside a dedicated event loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(run_processing_logic(bucket, key))

    except Exception as exc:
        logger.exception(f"Task failed for s3://{bucket}/{key}")
        raise self.retry(exc=exc)

    finally:
        loop.close()


async def run_processing_logic(bucket: str, key: str):
    """
    Async pipeline:
    1. Skip already processed images
    2. Download image from S3
    3. Generate thumbnail
    4. Upload thumbnail
    5. Move/process original image
    6. Notify admin (optional)
    """

    # -------------------------------------------------
    # Idempotency guard
    # -------------------------------------------------
    if key.startswith("processed/"):
        return {"status": "skipped"}

    if hasattr(ImageService, "already_processed"):
        if await ImageService.already_processed(bucket, key):
            return {"status": "already_processed"}

    # -------------------------------------------------
    # 1. Download image
    # -------------------------------------------------
    image_data = await ImageService.download_image(bucket, key)

    # -------------------------------------------------
    # 2. Generate thumbnail (CPU-bound → offloaded)
    # -------------------------------------------------
    thumbnail_data = await asyncio.to_thread(_generate_thumbnail, image_data)

    # -------------------------------------------------
    # 3. Upload thumbnail
    # -------------------------------------------------
    thumbnail_key = f"thumbnails/{key.split('/')[-1]}"
    await ImageService.upload_thumbnail(bucket, thumbnail_key, thumbnail_data)

    # -------------------------------------------------
    # 4. Move / process original image
    # -------------------------------------------------
    success = await ImageService.process_image(bucket, key)

    if not success:
        raise RuntimeError(f"Failed to process image move for {bucket}/{key}")

    # -------------------------------------------------
    # 5. Notify admin (optional safe call)
    # -------------------------------------------------
    try:
        # Uncomment if needed
        # await EmailService.send_image_links(
        #     settings.ADMIN_EMAIL,
        #     [f"Original: {key}", f"Thumbnail: {thumbnail_key}"]
        # )

        logger.info(
            f"Processing complete for s3://{bucket}/{key} "
            f"(thumbnail: {thumbnail_key})"
        )

    except Exception as email_exc:
        # Email failure should NOT fail the whole job
        logger.warning(f"Email notification failed: {email_exc}")

    return {
        "status": "success",
        "bucket": bucket,
        "key": key,
        "thumbnail": thumbnail_key,
    }


def _generate_thumbnail(data: bytes) -> bytes:
    """
    CPU-bound image processing (runs in thread pool).
    """
    with PILImage.open(BytesIO(data)) as im:
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")

        im.thumbnail((128, 128))

        buffer = BytesIO()
        im.save(buffer, format="JPEG")

        return buffer.getvalue()