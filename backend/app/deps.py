#deps.py
from app.services.dynamo_service import DynamoService
from app.repository.dynamo_image_repo import DynamoImageRepository
from app.core.config import settings

_dynamo_service = None
_image_repo = None


def get_dynamo_service():
    global _dynamo_service
    if _dynamo_service is None:
        _dynamo_service = DynamoService(table_name=settings.DYNAMO_IMAGES_TABLE)
    return _dynamo_service


def get_image_repo():
    global _image_repo
    if _image_repo is None:
        _image_repo = DynamoImageRepository(get_dynamo_service())
    return _image_repo