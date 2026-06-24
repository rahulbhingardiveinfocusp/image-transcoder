from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "ImageTranscoder"

    # FIX: DATABASE_URL removed — no longer needed after Dynamo migration.
    # Keep it optional with None default if you want a zero-downtime cutover,
    # then delete it once Postgres is fully decommissioned.
    DATABASE_URL: Optional[str] = None

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    S3_BUCKET_NAME: str
    SQS_QUEUE_URL: str
    LOCALSTACK_ENDPOINT: str = ""

    # FIX: new required field for DynamoDB table
    DYNAMO_IMAGES_TABLE: str

    CELERY_QUEUE_NAME: str = "celery-task-queue"
    CELERY_TASK_QUEUE_URL: str

    localstack_auth_token: Optional[str] = None
    ADMIN_EMAIL: str
    USER_POOL_CLIENT_ID: Optional[str] = None
    USER_POOL_ID: Optional[str] = None

    class Config:
        env_file = ".env"


settings = Settings()