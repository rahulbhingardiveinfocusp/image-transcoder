import asyncio
import logging
import urllib.parse
from io import BytesIO

from PIL import Image as PILImage
from celery.exceptions import MaxRetriesExceededError

from app.tasks.celery_app import celery_app
from app.services.image_service import ImageService
from app.deps import get_image_repo
from app.dto.image import ProcessingStatus
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue=settings.CELERY_QUEUE_NAME,
)
def process_s3_upload_task(self, bucket: str, key: str):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_processing_logic(bucket, key))
    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.exception(
                "Max retries exceeded for s3://%s/%s — giving up.", bucket, key
            )
            raise
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


async def run_processing_logic(bucket: str, key: str) -> dict:
    decoded_key = urllib.parse.unquote(key)
    thumbnail_key: str | None = None

    # FIX: no engine/session — get the singleton DynamoImageRepository
    repo = get_image_repo()

    # -----------------------
    # ALREADY PROCESSED?
    # -----------------------
    if await ImageService.already_processed(repo, decoded_key):
        logger.info("[-] Already completed, skipping: %s", decoded_key)
        return {"status": "already_processed"}

    # -----------------------
    # FIND THE RECORD
    # -----------------------
    # FIX: was a raw `select(Image).where(...)` SQL query
    all_items = await repo.list_all()
    image_record = next((i for i in all_items if i.get("s3_key") == decoded_key), None)

    if not image_record:
        raise ValueError(f"No image found for key: {decoded_key}")

    image_id = image_record["id"]

    # -----------------------
    # MARK AS PROCESSING
    # -----------------------
    # FIX: was `image_record.status = ProcessingStatus.PROCESSING` + session.commit()
    await repo.update_status(image_id, ProcessingStatus.PROCESSING.value.upper())

    try:
        # -----------------------
        # DOWNLOAD → THUMBNAIL → UPLOAD
        # -----------------------
        image_data = await ImageService.download_image(bucket, decoded_key)
        if not image_data:
            raise RuntimeError(f"Key not found: {bucket}/{decoded_key}")

        thumbnail_data = await asyncio.to_thread(_generate_thumbnail, image_data)
        filename = decoded_key.split("/")[-1]
        thumbnail_key = f"thumbnails/{filename}"
        await ImageService.upload_thumbnail(bucket, thumbnail_key, thumbnail_data)

        # -----------------------
        # PROCESS (S3 copy raw → processed)
        # -----------------------
        # FIX: was `ImageService.process_image(session, ...)` — now passes repo
        new_key = await ImageService.process_image(repo, bucket, decoded_key)

        # -----------------------
        # MARK AS COMPLETED
        # -----------------------
        # FIX: was three separate ORM field assignments + session.commit()
        # update_status now accepts processed_key to do it in one write
        await repo.update_status(
            image_id,
            ProcessingStatus.COMPLETED.value.upper(),
            processed_key=thumbnail_key,
        )

    except Exception:
        # FIX: was `image_record.status = ProcessingStatus.FAILED` + session.commit()
        await repo.update_status(image_id, ProcessingStatus.FAILED.value.upper())
        raise

    logger.info(
        "[+] Task successful: s3://%s/%s -> %s", bucket, decoded_key, thumbnail_key
    )
    return {
        "status": "success",
        "bucket": bucket,
        "key": decoded_key,
        "thumbnail": thumbnail_key,
    }


def _generate_thumbnail(data: bytes) -> bytes:
    with PILImage.open(BytesIO(data)) as im:
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        im.thumbnail((128, 128))
        buf = BytesIO()
        im.save(buf, format="JPEG")
        return buf.getvalue()