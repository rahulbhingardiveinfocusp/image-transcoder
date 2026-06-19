from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from app.models.image import ProcessingStatus

class ImageResponse(BaseModel):
    id: UUID
    filename: str
    status: ProcessingStatus
    s3_key: str
    created_at: datetime
    url: str
    model_config = {
        "from_attributes": True
    }

class UploadRequest(BaseModel):
    filename: str
    content_type:str