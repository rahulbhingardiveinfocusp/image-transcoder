from app.services.dynamo_service import DynamoService
from app.repository.dynamo_image_repo import DynamoImageRepository

def get_image_repo():
    dynamo = DynamoService(table_name="images")
    return DynamoImageRepository(dynamo)