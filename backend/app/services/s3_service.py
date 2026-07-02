from venv import logger

import boto3
import logging
from app.core.config import settings
logger = logging.getLogger(__name__)
from botocore.config import Config
is_local = settings.LOCALSTACK_ENDPOINT is not None

# 1. INTERNAL: for boto3 calls
internal_endpoint = settings.LOCALSTACK_ENDPOINT

# 2. PUBLIC: what browser can access
public_endpoint = "http://localhost:4566" if is_local else None


class S3Service:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            endpoint_url=internal_endpoint,
            config=Config(
                signature_version="s3v4",
                s3={
                    # IMPORTANT FIX
                    "addressing_style": "path" if is_local else "virtual"
                },
            ),
        )

        self.public_endpoint = public_endpoint

    def make_public_url(self, url: str) -> str:
        if not self.public_endpoint:
            return url

        # replace internal host with browser-safe host
        return url.replace(settings.LOCALSTACK_ENDPOINT, self.public_endpoint)

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
                if content_type:
                    params["ContentType"] = content_type

            if method == "get_object":
                params["ResponseContentType"] = "image/jpeg"
                params["ResponseContentDisposition"] = "inline"

            url= self.s3.generate_presigned_url(
                ClientMethod=method,
                Params=params,
                ExpiresIn=expiration,
            )
            return self.make_public_url(url)
        except Exception as e:
            logger.error(f"Error generating presigned URL for {object_name}: {e}")
            raise

    def generate_upload_url(self, object_name: str, expiration: int = 3600):
        return self.generate_presigned_url(object_name, method="put_object", expiration=expiration)

    def generate_download_url(self, object_name: str, expiration: int = 3600):
        return self.generate_presigned_url(object_name, method="get_object", expiration=expiration)