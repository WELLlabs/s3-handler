"""
Pydantic models for request and response schemas.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response model for file upload."""

    message: str
    key: str
    bucket: str


class DownloadResponse(BaseModel):
    """Response model for file download."""

    message: str
    key: str
    bucket: str


class PresignedUploadResponse(BaseModel):
    """Response model for presigned upload URL."""

    upload_url: str
    key: str
    bucket: str
    expires_at: datetime


class PresignedDownloadResponse(BaseModel):
    """Response model for presigned download URL."""

    download_url: str
    key: str
    bucket: str
    expires_at: datetime


class UploadStatusRequest(BaseModel):
    """Request model for checking upload status."""

    key: str


class UploadStatusResponse(BaseModel):
    """Response model for upload status."""

    key: str
    exists: bool
    size: Optional[int] = None
    last_modified: Optional[datetime] = None
    etag: Optional[str] = None


class MultipartUploadInitRequest(BaseModel):
    """Request model for initiating multipart upload."""

    key: str
    content_type: Optional[str] = Field(default="application/octet-stream")


class MultipartUploadInitResponse(BaseModel):
    """Response model for multipart upload initiation."""

    upload_id: str
    key: str
    bucket: str


class MultipartUploadPartRequest(BaseModel):
    """Request model for uploading a part."""

    upload_id: str
    key: str
    part_number: int


class MultipartUploadPartResponse(BaseModel):
    """Response model for uploaded part."""

    part_number: int
    etag: str


class MultipartUploadCompleteRequest(BaseModel):
    """Request model for completing multipart upload."""

    upload_id: str
    key: str
    parts: list[dict[str, str | int]]  # List of {"etag": str, "part_number": int}


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: Optional[str] = None
