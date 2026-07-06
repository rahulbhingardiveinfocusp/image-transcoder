from typing import Optional

from pydantic_settings import BaseSettings

from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    PROJECT_NAME: str = "ImageTranscoder"
    AWS_REGION: str = "us-west-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    S3_BUCKET_NAME: str
    SQS_QUEUE_URL: str
    LOCALSTACK_ENDPOINT: str = ""
    DYNAMO_IMAGES_TABLE: str

    CELERY_QUEUE_NAME: str = "celery-task-queue"
    CELERY_TASK_QUEUE_URL: str

    localstack_auth_token: Optional[str] = None
    ADMIN_EMAIL: str
    USER_POOL_CLIENT_ID: Optional[str] = None
    USER_POOL_ID: Optional[str] = None
    REAL_AWS_ACCESS_KEY_ID: Optional[str] = None
    REAL_AWS_SECRET_ACCESS_KEY: Optional[str] = None
model_config = SettingsConfigDict(env_file=".env")


settings = Settings()