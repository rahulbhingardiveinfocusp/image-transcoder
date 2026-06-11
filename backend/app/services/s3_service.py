import boto3
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)
if settings.LOCALSTACK_ENDPOINT:
    endpoint_url = settings.LOCALSTACK_ENDPOINT
else:
    endpoint_url = f"https://s3.{settings.AWS_REGION}.amazonaws.com"
class S3Service:
    def __init__(self):

        self.s3 = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=boto3.session.Config(signature_version="s3v4"),
        )
    def generate_presigned_url(
    self,
    object_name: str,
    client_method: str = "put_object",
    expiration: int = 3600
    ):
        try:
            return self.s3.generate_presigned_url(
                ClientMethod=client_method,  # Pass as explicit keyword argument
                Params={
                    "Bucket": settings.S3_BUCKET_NAME,
                    "Key": object_name,
                },
                ExpiresIn=expiration
            )
        except Exception as e:
            logger.error(f"Error generating presigned URL for {object_name}: {e}")
            raise

    def generate_upload_url(self, object_name: str, expiration: int = 3600):
        return self.generate_presigned_url(object_name, 'put_object', expiration)

    def generate_download_url(self, object_name: str, expiration: int = 3600):
        return self.generate_presigned_url(object_name, 'get_object', expiration)