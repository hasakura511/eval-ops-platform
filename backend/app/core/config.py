"""
Application configuration.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Eval Ops Platform"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/evalops"
    
    # Storage
    STORAGE_TYPE: str = "local"  # "local" or "s3"
    STORAGE_PATH: str = "/app/artifacts"
    S3_BUCKET_NAME: str = ""
    S3_ENDPOINT_URL: str = ""
    
    # Auth (placeholder for future)
    SECRET_KEY: str = "changeme-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
