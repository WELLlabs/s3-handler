"""
Pytest configuration and fixtures.
"""

from unittest.mock import AsyncMock

import pytest

from app.services.s3_service import S3Service


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


@pytest.fixture
def sample_file_content():
    """Sample file content for testing."""
    return b"This is test file content for S3 operations."


@pytest.fixture
def sample_large_file_content():
    """Sample large file content for testing multipart upload."""
    # Create 60MB file to trigger multipart upload
    return b"0" * (60 * 1024 * 1024)


@pytest.fixture
def sample_key():
    """Sample S3 key for testing."""
    return "test-folder/test-file.txt"


@pytest.fixture
def sample_upload_response():
    """Sample upload response for testing."""
    return {
        "message": "File uploaded successfully",
        "key": "test-folder/test-file.txt",
        "bucket": "test-bucket",
    }


@pytest.fixture
def sample_presigned_url_response():
    """Sample presigned URL response for testing."""
    from datetime import datetime, timedelta

    return {
        "upload_url": "https://test-bucket.s3.amazonaws.com/test-file.txt?X-Amz-Signature=xxx",
        "key": "test-file.txt",
        "bucket": "test-bucket",
        "expires_at": datetime.utcnow() + timedelta(minutes=60),
    }


@pytest.fixture
def mock_s3_service(mock_s3_client):
    """Mock S3 service for testing."""
    service = S3Service()
    service._get_s3_client = AsyncMock(return_value=mock_s3_client)
    return service
