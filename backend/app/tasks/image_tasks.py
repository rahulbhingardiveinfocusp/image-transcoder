import asyncio
import traceback
import logging
logger = logging.getLogger(__name__)
from app.core.database import AsyncSessionLocal
from app.tasks.celery_app import celery_app

from app.services.image_service import ImageService
import asyncio
from functools import wraps

def async_task(f):
    @wraps(f)
    async def wrapper(*args, **kwargs):
        # Create a new loop for this specific task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    return wrapper

@celery_app.task(bind=True, max_retries=1)
@async_task
async def process_s3_upload_task(self, bucket: str, key: str):
    if key.startswith("processed/"):
        logger.info(f"Skipping key {key} because it is already processed.")
        return {"status": "skipped"}
    
    async def run_processing():
        try:
            # We no longer pass the DB object; the service handles its own sessions
            success = await ImageService.process_image(bucket, key)
            if not success:
                raise Exception("Image processing failed.")
            logger.info("ImageService completed successfully.")
        except Exception as e:
            error_msg = traceback.format_exc()
            logger.critical(f"CRITICAL ERROR in task: {error_msg}")
            raise e

    asyncio.run(run_processing())
    return {"status": "success", "key": key}