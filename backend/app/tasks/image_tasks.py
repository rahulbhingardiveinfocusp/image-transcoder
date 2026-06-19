import asyncio
import logging
import urllib.parse
from io import BytesIO
from PIL import Image as PILImage
from sqlalchemy import select
from app.models.image import Image
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.tasks.celery_app import celery_app
from app.services.image_service import ImageService
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
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=1,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            if await ImageService.already_processed(session, bucket, decoded_key):
                logger.info("[-] Already completed, skipping: %s", decoded_key)
                return {"status": "already_processed"}
            image_data = await ImageService.download_image(bucket, decoded_key)
            thumbnail_data = await asyncio.to_thread(_generate_thumbnail, image_data)
            filename = decoded_key.split("/")[-1]
            thumbnail_key = f"thumbnails/{filename}"
            await ImageService.upload_thumbnail(bucket, thumbnail_key, thumbnail_data,decoded_key,session)
            success = await ImageService.process_image(session, bucket, decoded_key)
            if not success:
                raise RuntimeError(
                    f"Failed to finalise processing for {bucket}/{decoded_key}"
                )
            result = await session.execute(
            select(Image).where(Image.s3_key == decoded_key)
            )
            image_record = result.scalars().first()
            if not image_record:
                raise ValueError(f"No image found for key: {decoded_key}")
            image_record.s3_processed_file =  thumbnail_key
            session.add(image_record)
            await session.flush()
            await session.commit()

    finally:
        await engine.dispose()

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