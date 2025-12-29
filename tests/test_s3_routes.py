"""
Tests for S3 API routes.
"""

import datetime
from io import BytesIO
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from main import create_app


class TestS3Routes:
    """Test cases for S3 API routes."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    @pytest.fixture
    def jwt_token(self):
        """Create a test JWT token."""
        settings = get_settings()
        token = jwt.encode(
            {
                "bucket": "test-bucket",
                "region": "us-east-1",
                "exp": datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(minutes=10),
            },
            settings.secret,
            algorithm="HS256",
        )
        return token

    @pytest.mark.asyncio
    async def test_access_token_endpoint(self, client):
        """Test access token generation endpoint."""
        response = client.post(
            "/access-token",
            params={"s3_region": "us-east-1", "s3_bucket": "test-bucket"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data

        # Verify token can be decoded
        settings = get_settings()
        payload = jwt.decode(data["token"], settings.secret, algorithms=["HS256"])
        assert payload["bucket"] == "test-bucket"
        assert payload["region"] == "us-east-1"
        assert "exp" in payload

    @pytest.mark.asyncio
    async def test_upload_file_direct_endpoint(self, client, jwt_token):
        """Test direct upload endpoint."""
        mock_result = {
            "message": "File uploaded successfully",
            "key": "test-file.txt",
            "bucket": "test-bucket",
        }

        with patch(
            "app.routers.s3_routes.s3_service.upload_file_direct",
            new_callable=AsyncMock,
        ) as mock_upload:
            mock_upload.return_value = mock_result

            response = client.post(
                "/upload",
                files={"file": ("test.txt", BytesIO(b"test content"), "text/plain")},
                params={"key": "test-file.txt", "token": jwt_token},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["key"] == "test-file.txt"
            assert "message" in data

    @pytest.mark.asyncio
    async def test_upload_file_direct_invalid_token(self, client):
        """Test upload endpoint with invalid token."""
        mock_result = {
            "message": "File uploaded successfully",
            "key": "test-file.txt",
            "bucket": "test-bucket",
        }

        with patch(
            "app.routers.s3_routes.s3_service.upload_file_direct",
            new_callable=AsyncMock,
        ) as mock_upload:
            mock_upload.return_value = mock_result

            response = client.post(
                "/upload",
                files={"file": ("test.txt", BytesIO(b"test content"), "text/plain")},
                params={"key": "test-file.txt", "token": "invalid-token"},
            )

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_file_direct_expired_token(self, client):
        """Test upload endpoint with expired token."""
        settings = get_settings()
        expired_token = jwt.encode(
            {
                "bucket": "test-bucket",
                "region": "us-east-1",
                "exp": datetime.datetime.now(datetime.UTC)
                - datetime.timedelta(minutes=1),
            },
            settings.secret,
            algorithm="HS256",
        )

        response = client.post(
            "/upload",
            files={"file": ("test.txt", BytesIO(b"test content"), "text/plain")},
            params={"key": "test-file.txt", "token": expired_token},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_download_file_direct_endpoint(self, client, jwt_token):
        """Test direct download endpoint."""
        mock_content = b"test file content"

        with patch(
            "app.routers.s3_routes.s3_service.download_file_direct",
            new_callable=AsyncMock,
        ) as mock_download:
            mock_download.return_value = mock_content

            response = client.get(
                "/download/test-file.txt", params={"token": jwt_token}
            )

            assert response.status_code == 200
            assert response.content == mock_content

    @pytest.mark.asyncio
    async def test_download_file_direct_invalid_token(self, client):
        """Test download endpoint with invalid token."""
        mock_content = b"test file content"

        with patch(
            "app.routers.s3_routes.s3_service.download_file_direct",
            new_callable=AsyncMock,
        ) as mock_download:
            mock_download.return_value = mock_content

            response = client.get(
                "/download/test-file.txt", params={"token": "invalid-token"}
            )

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_presigned_upload_url_endpoint(self, client):
        """Test presigned upload URL endpoint."""
        from datetime import UTC, datetime, timedelta

        mock_result = {
            "upload_url": "https://test-bucket.s3.amazonaws.com/test-file.txt",
            "key": "test-file.txt",
            "bucket": "test-bucket",
            "expires_at": datetime.now(UTC) + timedelta(minutes=60),
        }

        with patch(
            "app.routers.s3_routes.s3_service.generate_presigned_upload_url",
            new_callable=AsyncMock,
        ) as mock_presigned:
            mock_presigned.return_value = mock_result

            response = client.post(
                "/presigned/upload",
                params={
                    "key": "test-file.txt",
                    "s3_region": "us-east-1",
                    "s3_bucket": "test-bucket",
                    "content_type": "text/plain",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "upload_url" in data
            assert data["key"] == "test-file.txt"

    @pytest.mark.asyncio
    async def test_get_presigned_download_url_endpoint(self, client):
        """Test presigned download URL endpoint."""
        from datetime import UTC, datetime, timedelta

        mock_result = {
            "download_url": "https://test-bucket.s3.amazonaws.com/test-file.txt",
            "key": "test-file.txt",
            "bucket": "test-bucket",
            "expires_at": datetime.now(UTC) + timedelta(minutes=60),
        }

        with patch(
            "app.routers.s3_routes.s3_service.generate_presigned_download_url",
            new_callable=AsyncMock,
        ) as mock_presigned:
            mock_presigned.return_value = mock_result

            response = client.get(
                "/presigned/download/test-file.txt",
                params={"s3_region": "us-east-1", "s3_bucket": "test-bucket"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "download_url" in data
            assert data["key"] == "test-file.txt"

    @pytest.mark.asyncio
    async def test_check_upload_status_endpoint(self, client):
        """Test upload status check endpoint."""
        mock_result = {
            "key": "test-file.txt",
            "exists": True,
            "size": 1024,
            "last_modified": "2024-01-01T00:00:00",
            "etag": "test-etag",
        }

        with patch(
            "app.routers.s3_routes.s3_service.check_upload_status",
            new_callable=AsyncMock,
        ) as mock_status:
            mock_status.return_value = mock_result

            response = client.get(
                "/status",
                params={
                    "key": "test-file.txt",
                    "s3_region": "us-east-1",
                    "s3_bucket": "test-bucket",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["exists"] is True
            assert data["size"] == 1024

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    def test_health_check_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_upload_file_error_handling(self, client, jwt_token):
        """Test error handling for upload endpoint."""
        with patch(
            "app.routers.s3_routes.s3_service.upload_file_direct",
            new_callable=AsyncMock,
        ) as mock_upload:
            mock_upload.side_effect = ValueError("Upload failed")

            response = client.post(
                "/upload",
                files={"file": ("test.txt", BytesIO(b"test content"), "text/plain")},
                params={"key": "test-file.txt", "token": jwt_token},
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_download_file_not_found_error(self, client, jwt_token):
        """Test error handling for download when file not found."""
        with patch(
            "app.routers.s3_routes.s3_service.download_file_direct",
            new_callable=AsyncMock,
        ) as mock_download:
            mock_download.side_effect = ValueError("File not found")

            response = client.get(
                "/download/non-existent-file.txt", params={"token": jwt_token}
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_file_endpoint(self, client):
        """Test successful file deletion endpoint."""
        mock_result = {
            "message": "File deleted successfully",
            "key": "test-file.txt",
            "bucket": "test-bucket",
            "deleted": True,
        }

        with patch(
            "app.routers.s3_routes.s3_service.delete_file",
            new_callable=AsyncMock,
        ) as mock_delete:
            mock_delete.return_value = mock_result

            response = client.delete(
                "/delete",
                params={
                    "key": "test-file.txt",
                    "s3_region": "us-east-1",
                    "s3_bucket": "test-bucket",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["key"] == "test-file.txt"
            assert data["deleted"] is True
            assert "message" in data

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, client):
        """Test delete endpoint when file doesn't exist."""
        mock_result = {
            "message": "Failed: File does not exist",
            "key": "non-existent-file.txt",
            "bucket": "test-bucket",
            "deleted": False,
        }

        with patch(
            "app.routers.s3_routes.s3_service.delete_file",
            new_callable=AsyncMock,
        ) as mock_delete:
            mock_delete.return_value = mock_result

            response = client.delete(
                "/delete",
                params={
                    "key": "non-existent-file.txt",
                    "s3_region": "us-east-1",
                    "s3_bucket": "test-bucket",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["deleted"] is False
            assert "does not exist" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_delete_file_error_handling(self, client):
        """Test error handling for delete endpoint."""
        with patch(
            "app.routers.s3_routes.s3_service.delete_file",
            new_callable=AsyncMock,
        ) as mock_delete:
            mock_delete.side_effect = ValueError("Delete failed")

            response = client.delete(
                "/delete",
                params={
                    "key": "test-file.txt",
                    "s3_region": "us-east-1",
                    "s3_bucket": "test-bucket",
                },
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_file_general_error(self, client):
        """Test general exception handling for delete endpoint."""
        with patch(
            "app.routers.s3_routes.s3_service.delete_file",
            new_callable=AsyncMock,
        ) as mock_delete:
            mock_delete.side_effect = Exception("Unexpected error")

            response = client.delete(
                "/delete",
                params={
                    "key": "test-file.txt",
                    "s3_region": "us-east-1",
                    "s3_bucket": "test-bucket",
                },
            )

            assert response.status_code == 500
