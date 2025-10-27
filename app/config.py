"""
Application configuration using Pydantic settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AWS S3 Configuration
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_default_region: str
    aws_default_bucket: str

    # Multipart upload configuration
    multipart_chunk_size_mb: int = 50  # 50MB chunks
    max_part_number: int = 10000
    presigned_url_expiration_minutes: int = 60

    # Retry configuration
    max_retries: int = 3
    retry_delay_seconds: float = 2.0

    # Timeout configuration
    upload_timeout_seconds: int = 300  # 5 minutes
    download_timeout_seconds: int = 300

    # Application configuration
    app_name: str = "AWS S3 Handler API"
    version: str = "1.0.0"
    port: int = 8000
    host: str = "0.0.0.0"
    reload: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
