import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProcessingStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageResponse(BaseModel):
    id: UUID
    filename: str
    status: ProcessingStatus
    created_at: datetime
    url: str
    s3_key: str

    model_config = {"from_attributes": True}


class UploadRequest(BaseModel):
    filename: str
    content_type: str