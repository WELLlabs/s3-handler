"""
API routes for S3 operations.
"""

import datetime
import logging

import jwt
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.models import (
    DeleteResponse,
    PresignedDownloadResponse,
    PresignedUploadResponse,
    UploadResponse,
    UploadStatusResponse,
)
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)
router = APIRouter()
s3_service = S3Service()


@router.post("/access-token")
async def tokenize(s3_region: str, s3_bucket: str):
    """
    Generate JWT access token with S3 region and bucket information.

    Args:
        s3_region: AWS region name
        s3_bucket: S3 bucket name

    Returns:
        Dict with JWT token
    """
    try:
        logger.info(
            f"Generating access token for bucket: {s3_bucket}, region: {s3_region}"
        )
        settings = get_settings()
        expiration_minutes = settings.jwt_expiration_minutes
        logger.info(f"Token expiration set to {expiration_minutes} minutes")
        token = jwt.encode(
            {
                "bucket": s3_bucket,
                "region": s3_region,
                "exp": datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(minutes=expiration_minutes),
            },
            settings.secret,
            algorithm="HS256",
        )
        logger.info(f"Successfully generated access token for bucket: {s3_bucket}")
        return {"token": token}
    except Exception as e:
        logger.error(f"Failed to generate access token: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate token: {str(e)}"
        )


@router.post("/upload", response_model=UploadResponse)
async def upload_file_direct(file: UploadFile, key: str, token: str):
    """
    Upload file directly to S3 using multipart upload for large files.

    Args:
        file: Uploaded file
        key: S3 object key (path in bucket)
        token: JWT token containing bucket and region information

    Returns:
        Upload confirmation
    """
    try:
        logger.info(f"Received upload request for key: {key}")
        # Decode token to get bucket and region
        settings = get_settings()
        try:
            payload = jwt.decode(token, settings.secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            logger.error("Token expired for upload request")
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token for upload request: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

        bucket = payload["bucket"]
        region = payload["region"]
        logger.info(f"Decoded token - bucket: {bucket}, region: {region}")

        # Read file content
        file_content = await file.read()

        # Upload to S3
        result = await s3_service.upload_file_direct(
            file_content=file_content,
            key=key,
            bucket=bucket,
            region=region,
            content_type=file.content_type or "application/octet-stream",
        )

        return UploadResponse(**result)
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/download/{key:path}")
async def download_file_direct(key: str, token: str):
    """
    Download file directly from S3.

    Args:
        key: S3 object key (path in bucket)
        token: JWT token containing bucket and region information

    Returns:
        File content as stream
    """
    try:
        logger.info(f"Received download request for key: {key}")
        # Decode token to get bucket and region
        settings = get_settings()
        try:
            payload = jwt.decode(token, settings.secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            logger.error("Token expired for download request")
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token for download request: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

        bucket = payload["bucket"]
        region = payload["region"]
        logger.info(f"Decoded token - bucket: {bucket}, region: {region}")

        # Download from S3
        file_content = await s3_service.download_file_direct(
            key=key, bucket=bucket, region=region
        )

        # Return as streaming response
        return StreamingResponse(
            iter([file_content]),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{key.split("/")[-1]}"'
            },
        )
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected download error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/presigned/upload", response_model=PresignedUploadResponse)
async def get_presigned_upload_url(
    key: str,
    s3_region: str,
    s3_bucket: str,
    content_type: str = "application/octet-stream",
):
    """
    Generate presigned URL for uploading file to S3.

    Args:
        key: S3 object key (path in bucket)
        s3_region: AWS region name
        s3_bucket: S3 bucket name
        content_type: Content type of the file

    Returns:
        Presigned upload URL and metadata
    """
    try:
        logger.info(
            f"Generating presigned upload URL for key: {key}, bucket: {s3_bucket}, region: {s3_region}"
        )
        result = await s3_service.generate_presigned_upload_url(
            key=key, bucket=s3_bucket, region=s3_region, content_type=content_type
        )
        return PresignedUploadResponse(**result)
    except ValueError as e:
        logger.error(f"Presigned upload URL error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/presigned/download/{key:path}", response_model=PresignedDownloadResponse)
async def get_presigned_download_url(key: str, s3_region: str, s3_bucket: str):
    """
    Generate presigned URL for downloading file from S3.

    Args:
        key: S3 object key (path in bucket)
        s3_region: AWS region name
        s3_bucket: S3 bucket name

    Returns:
        Presigned download URL and metadata
    """
    try:
        logger.info(
            f"Generating presigned download URL for key: {key}, bucket: {s3_bucket}, region: {s3_region}"
        )
        result = await s3_service.generate_presigned_download_url(
            key=key, bucket=s3_bucket, region=s3_region
        )
        return PresignedDownloadResponse(**result)
    except ValueError as e:
        logger.error(f"Presigned download URL error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/status", response_model=UploadStatusResponse)
async def check_upload_status(key: str, s3_region: str, s3_bucket: str):
    """
    Check status of uploaded file.

    Args:
        key: S3 object key (path in bucket)
        s3_region: AWS region name
        s3_bucket: S3 bucket name

    Returns:
        Upload status information
    """
    try:
        logger.info(
            f"Checking upload status for key: {key}, bucket: {s3_bucket}, region: {s3_region}"
        )
        result = await s3_service.check_upload_status(
            key=key, bucket=s3_bucket, region=s3_region
        )
        return UploadStatusResponse(**result)
    except ValueError as e:
        logger.error(f"Status check error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/delete", response_model=DeleteResponse)
async def delete_file(key: str, s3_region: str, s3_bucket: str):
    """
    Delete file from S3.

    Args:
        key: S3 object key (path in bucket)
        s3_region: AWS region name
        s3_bucket: S3 bucket name

    Returns:
        Delete confirmation with deleted status
    """
    try:
        logger.info(
            f"Received delete request for key: {key}, bucket: {s3_bucket}, region: {s3_region}"
        )
        result = await s3_service.delete_file(
            key=key, bucket=s3_bucket, region=s3_region
        )
        return DeleteResponse(**result)
    except ValueError as e:
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
