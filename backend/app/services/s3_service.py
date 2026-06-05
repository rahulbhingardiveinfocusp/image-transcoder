import boto3
from app.core.config import settings

class S3Service:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            # Boto3 automatically picks up credentials from env vars 
            # if they are set in the environment.
            endpoint_url="http://localhost:4566",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None
        )
    
    def generate_presigned_url(self, object_name: str, expiration=3600):
        return self.s3.generate_presigned_url(
            'put_object',
            Params={'Bucket': settings.S3_BUCKET_NAME, 'Key': object_name},
            ExpiresIn=expiration
        )
    def generate_download_url(self, object_name: str, expiration=3600):
        """
        Generates a presigned URL to share a file publicly for a limited time.
        """
        return self.s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.S3_BUCKET_NAME, 
                'Key': object_name
            },
            ExpiresIn=expiration
        )