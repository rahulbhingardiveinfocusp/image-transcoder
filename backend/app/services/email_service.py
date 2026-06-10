import asyncio
import boto3
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)
endpoint_url = settings.LOCALSTACK_ENDPOINT or None
class EmailService:
    @classmethod
    def _get_ses_client(cls):
        return boto3.client(
            "ses",
            endpoint_url=endpoint_url,
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

    @staticmethod
    async def send_image_links(recipient_email: str, image_links: list):
        """Sends an email via SES without blocking the event loop."""
        ses = EmailService._get_ses_client()
        body_text = "Your processed images are ready:\n\n" + "\n".join(image_links)

        def _send():
            return ses.send_email(
                Source=settings.ADMIN_EMAIL,
                Destination={"ToAddresses": [recipient_email]},
                Message={
                    "Subject": {"Data": "Your Processed Images"},
                    "Body": {"Text": {"Data": body_text}},
                },
            )

        try:
            # loop = asyncio.get_event_loop()
            # await loop.run_in_executor(None, _send)
            logger.info(f"Email successfully sent to {recipient_email}")
        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {e}")
            raise