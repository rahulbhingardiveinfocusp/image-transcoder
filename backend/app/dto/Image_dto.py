from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from app.models.image import ProcessingStatus

class ImageResponse(BaseModel):
    id: UUID
    filename: str
    status: ProcessingStatus
    created_at: datetime
    url: str
    s3_Key:str
    model_config = {
        "from_attributes": True
    }

class UploadRequest(BaseModel):
    filename: str
    content_type:str