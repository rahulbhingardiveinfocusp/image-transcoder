import boto3
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

endpoint_url = settings.LOCALSTACK_ENDPOINT if settings.LOCALSTACK_ENDPOINT else None


class S3Service:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            endpoint_url=endpoint_url,
            config=boto3.session.Config(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
            ),
        )

    def generate_presigned_url(
        self,
        object_name: str,
        content_type: str | None = None,
        method: str = "put_object",
        expiration: int = 3600,
    ):
        try:
            params = {
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": object_name,
            }

            if method == "put_object":
                # ContentType on upload so S3 stores the correct MIME type
                if content_type:
                    params["ContentType"] = content_type

            if method == "get_object":
                # FIX: ResponseContent* are only valid for get_object, not put_object
                params["ResponseContentType"] = "image/jpeg"
                params["ResponseContentDisposition"] = "inline"

            return self.s3.generate_presigned_url(
                ClientMethod=method,
                Params=params,
                ExpiresIn=expiration,
            )
        except Exception as e:
            logger.error(f"Error generating presigned URL for {object_name}: {e}")
            raise

    def generate_upload_url(self, object_name: str, expiration: int = 3600):
        return self.generate_presigned_url(object_name, method="put_object", expiration=expiration)

    def generate_download_url(self, object_name: str, expiration: int = 3600):
        return self.generate_presigned_url(object_name, method="get_object", expiration=expiration)