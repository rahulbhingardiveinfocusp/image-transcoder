from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "ImageTranscoder"
    DATABASE_URL: str
    localstack_auth_token: str | None = None
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""   # Optional for local, used if not using ~/.aws/credentials
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    SQS_QUEUE_URL: str
    S3_BUCKET_NAME: str
    LOCALSTACK_ENDPOINT: str
    ADMIN_EMAIL:str
    CELERY_QUEUE_NAME: str = "celery-task-queue" 
    CELERY_TASK_QUEUE_URL: str  
    
    class Config:
        env_file = ".env"

settings = Settings()