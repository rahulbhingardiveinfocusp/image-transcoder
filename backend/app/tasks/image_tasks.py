import asyncio
import traceback
import logging
import os
from io import BytesIO
from PIL import Image as PILImage
from app.tasks.celery_app import celery_app
from app.services.image_service import ImageService

logger = logging.getLogger(__name__)

# This is the entry point that Celery calls
@celery_app.task(bind=True, max_retries=1)
def process_s3_upload_task(self, bucket: str, key: str):
    # We use asyncio.run to bridge the sync Celery worker with your async code
    return asyncio.run(run_processing_logic(bucket, key))

# This is your actual async processing logic
async def run_processing_logic(bucket, key):
    if key.startswith("processed/"):
        logger.info(f"Skipping key {key} because it is already processed.")
        return {"status": "skipped"}
    
    try:
        logger.info(f"--- Starting pipeline for: {key} ---")
        
        # 1. Download
        image_data = await ImageService.download_image(bucket, key)
        logger.info(f"Downloaded {len(image_data)} bytes")
        
        # 2. Thumbnail Generation
        size = (128, 128)
        with PILImage.open(BytesIO(image_data)) as im:
            # Convert to RGB if the image has an Alpha channel (RGBA)
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGB")
                
            im.thumbnail(size)
            buffer = BytesIO()
            im.save(buffer, format="JPEG")
            thumbnail_data = buffer.getvalue()
        
        # 3. Upload Thumbnail
        thumbnail_key = f"thumbnails/{os.path.basename(key)}"
        await ImageService.upload_thumbnail(bucket, thumbnail_key, thumbnail_data)
        logger.info(f"Thumbnail created at: {thumbnail_key}")
        
        # 4. Finalize & Move
        success = await ImageService.process_image(bucket, key)
        if not success:
            raise Exception("Image moving/processing failed.")
        
        logger.info("--- Pipeline Completed Successfully ---")
        return {"status": "success", "key": key}
            
    except Exception as e:
        logger.critical(f"Pipeline failed: {traceback.format_exc()}")
        raise e