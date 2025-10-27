"""
API routes for S3 operations.
"""

import logging

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.models import (
    PresignedDownloadResponse,
    PresignedUploadResponse,
    UploadResponse,
    UploadStatusRequest,
    UploadStatusResponse,
)
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)
router = APIRouter()  # prefix="/api/s3", tags=["S3 Operations"])
s3_service = S3Service()


@router.post("/upload", response_model=UploadResponse)
async def upload_file_direct(file: UploadFile, key: str):
    """
    Upload file directly to S3 using multipart upload for large files.

    Args:
        file: Uploaded file
        key: S3 object key (path in bucket)

    Returns:
        Upload confirmation
    """
    try:
        # Read file content
        file_content = await file.read()

        # Upload to S3
        result = await s3_service.upload_file_direct(
            file_content=file_content,
            key=key,
            content_type=file.content_type or "application/octet-stream",
        )

        return UploadResponse(**result)
    except ValueError as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/download/{key:path}")
async def download_file_direct(key: str):
    """
    Download file directly from S3.

    Args:
        key: S3 object key (path in bucket)

    Returns:
        File content as stream
    """
    try:
        # Download from S3
        file_content = await s3_service.download_file_direct(key=key)

        # Return as streaming response
        return StreamingResponse(
            iter([file_content]),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{key.split("/")[-1]}"'
            },
        )
    except ValueError as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected download error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/presigned/upload", response_model=PresignedUploadResponse)
async def get_presigned_upload_url(
    key: str, content_type: str = "application/octet-stream"
):
    """
    Generate presigned URL for uploading file to S3.

    Args:
        key: S3 object key (path in bucket)
        content_type: Content type of the file

    Returns:
        Presigned upload URL and metadata
    """
    try:
        result = await s3_service.generate_presigned_upload_url(
            key=key, content_type=content_type
        )
        return PresignedUploadResponse(**result)
    except ValueError as e:
        logger.error(f"Presigned upload URL error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/presigned/download/{key:path}", response_model=PresignedDownloadResponse)
async def get_presigned_download_url(key: str):
    """
    Generate presigned URL for downloading file from S3.

    Args:
        key: S3 object key (path in bucket)

    Returns:
        Presigned download URL and metadata
    """
    try:
        result = await s3_service.generate_presigned_download_url(key=key)
        return PresignedDownloadResponse(**result)
    except ValueError as e:
        logger.error(f"Presigned download URL error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/status", response_model=UploadStatusResponse)
async def check_upload_status(request: UploadStatusRequest):
    """
    Check status of uploaded file.

    Args:
        request: Request with key

    Returns:
        Upload status information
    """
    try:
        result = await s3_service.check_upload_status(key=request.key)
        return UploadStatusResponse(**result)
    except ValueError as e:
        logger.error(f"Status check error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
