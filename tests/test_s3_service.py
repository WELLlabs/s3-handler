"""
Tests for S3 service.
"""

from unittest.mock import AsyncMock, patch

import pytest
from botocore.exceptions import ClientError


class TestS3Service:
    """Test cases for S3 service."""

    @pytest.mark.asyncio
    async def test_upload_file_direct_small_file(
        self, mock_s3_service, sample_file_content, sample_key
    ):
        """Test uploading a small file directly to S3."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_s3_service._get_s3_client = AsyncMock(return_value=mock_client)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock upload_fileobj
        with patch.object(mock_client, "upload_fileobj", new_callable=AsyncMock):
            result = await mock_s3_service.upload_file_direct(
                file_content=sample_file_content,
                key=sample_key,
                content_type="text/plain",
            )

            assert result["key"] == sample_key
            assert "message" in result
            assert "bucket" in result

    @pytest.mark.asyncio
    async def test_upload_file_direct_large_file_multipart(
        self, mock_s3_service, sample_large_file_content, sample_key
    ):
        """Test uploading a large file using multipart upload."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_s3_service._get_s3_client = AsyncMock(return_value=mock_client)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock multipart upload responses
        mock_client.create_multipart_upload.return_value = {
            "UploadId": "test-upload-id"
        }
        mock_client.upload_part.return_value = {"ETag": '"test-etag"'}
        mock_client.complete_multipart_upload.return_value = {"ETag": '"final-etag"'}

        with patch.object(
            mock_s3_service, "_upload_part", new_callable=AsyncMock
        ) as mock_upload_part:
            mock_upload_part.return_value = {"etag": "test-etag", "part_number": 1}

            result = await mock_s3_service.upload_file_direct(
                file_content=sample_large_file_content,
                key=sample_key,
                content_type="application/octet-stream",
            )

            assert result["key"] == sample_key
            assert "etag" in result
            assert "multipart upload" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_download_file_direct(
        self, mock_s3_service, sample_file_content, sample_key
    ):
        """Test downloading a file directly from S3."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_s3_service._get_s3_client = AsyncMock(return_value=mock_client)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock get_object response
        mock_body = AsyncMock()
        mock_body.read.return_value = sample_file_content
        mock_client.get_object.return_value = {"Body": mock_body}

        result = await mock_s3_service.download_file_direct(key=sample_key)

        assert result == sample_file_content

    @pytest.mark.asyncio
    async def test_download_file_not_found(self, mock_s3_service, sample_key):
        """Test downloading a file that doesn't exist."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_s3_service._get_s3_client = AsyncMock(return_value=mock_client)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock ClientError for NoSuchKey
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_client.get_object.side_effect = ClientError(error_response, "get_object")

        with pytest.raises(ValueError):
            await mock_s3_service.download_file_direct(key=sample_key)

    @pytest.mark.asyncio
    async def test_generate_presigned_upload_url(self, mock_s3_service, sample_key):
        """Test generating presigned upload URL."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_s3_service._get_s3_client = AsyncMock(return_value=mock_client)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock generate_presigned_url
        mock_url = "https://test-bucket.s3.amazonaws.com/test-file.txt"
        mock_client.generate_presigned_url.return_value = mock_url

        result = await mock_s3_service.generate_presigned_upload_url(
            key=sample_key, content_type="text/plain"
        )

        assert "upload_url" in result
        assert "expires_at" in result
        assert result["key"] == sample_key

    @pytest.mark.asyncio
    async def test_generate_presigned_download_url(self, mock_s3_service, sample_key):
        """Test generating presigned download URL."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_s3_service._get_s3_client = AsyncMock(return_value=mock_client)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock generate_presigned_url
        mock_url = "https://test-bucket.s3.amazonaws.com/test-file.txt"
        mock_client.generate_presigned_url.return_value = mock_url

        result = await mock_s3_service.generate_presigned_download_url(key=sample_key)

        assert "download_url" in result
        assert "expires_at" in result
        assert result["key"] == sample_key

    @pytest.mark.asyncio
    async def test_check_upload_status_exists(self, mock_s3_service, sample_key):
        """Test checking upload status for existing file."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_s3_service._get_s3_client = AsyncMock(return_value=mock_client)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock head_object response
        from datetime import UTC, datetime

        mock_client.head_object.return_value = {
            "ContentLength": 1024,
            "LastModified": datetime.now(UTC),
            "ETag": '"test-etag"',
        }

        result = await mock_s3_service.check_upload_status(key=sample_key)

        assert result["exists"] is True
        assert result["size"] == 1024
        assert result["etag"] == "test-etag"

    @pytest.mark.asyncio
    async def test_check_upload_status_not_exists(self, mock_s3_service, sample_key):
        """Test checking upload status for non-existing file."""
        # Mock S3 client
        mock_client = AsyncMock()
        mock_s3_service._get_s3_client = AsyncMock(return_value=mock_client)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock ClientError for 404
        error_response = {"Error": {"Code": "404", "Message": "Not found"}}
        mock_client.head_object.side_effect = ClientError(error_response, "head_object")

        result = await mock_s3_service.check_upload_status(key=sample_key)

        assert result["exists"] is False
        assert result["size"] is None
        assert result["etag"] is None
