import boto3
from app.core.config import settings

class EmailService:
    @staticmethod
    def send_image_links(recipient_email: str, image_links: list):
        # LocalStack/AWS SES Client
        ses = boto3.client(
            "ses",
            endpoint_url="http://localhost:4566", # LocalStack endpoint
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

        body_text = "Your processed images are ready:\n\n" + "\n".join(image_links)

        ses.send_email(
            Source="notifications@yourdomain.com",
            Destination={"ToAddresses": [recipient_email]},
            Message={
                "Subject": {"Data": "Your Processed Images"},
                "Body": {"Text": {"Data": body_text}},
            },
        )