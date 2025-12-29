"""
S3 service for handling file uploads and downloads.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from aioboto3 import Session
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for handling S3 operations."""

    def __init__(self):
        """Initialize S3 service with settings."""
        self.settings = get_settings()
        self.session = Session()

    async def _get_s3_client(self, region: str):
        """
        Get configured S3 client.

        If AWS credentials are provided in environment variables, they will be used.
        Otherwise, the client will use IAM role credentials from EC2 instance metadata.

        Args:
            region: AWS region name

        Returns:
            Configured S3 client
        """
        # Build client arguments
        client_kwargs = {
            "region_name": region,
        }

        # Only include credentials if they are explicitly provided
        # If not provided, boto3/aioboto3 will use IAM role credentials automatically
        if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
            logger.info("Using explicit AWS credentials from environment variables")
            client_kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key
        else:
            logger.info(
                "AWS credentials not provided, using IAM role credentials from EC2 instance metadata"
            )

        return self.session.client("s3", **client_kwargs)

    async def _upload_part(
        self,
        s3_client,
        bucket: str,
        key: str,
        upload_id: str,
        part_number: int,
        data: bytes,
    ) -> dict:
        """
        Upload a single part of a multipart upload.

        Args:
            s3_client: boto3 S3 client
            bucket: S3 bucket name
            key: S3 object key
            upload_id: Multipart upload ID
            part_number: Part number (1-based)
            data: Binary data for the part

        Returns:
            Dict with etag and part_number
        """
        try:
            response = await s3_client.upload_part(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=data,
            )
            return {"etag": response["ETag"].strip('"'), "part_number": part_number}
        except Exception as e:
            logger.error(f"Error uploading part {part_number}: {str(e)}")
            raise

    async def _chunk_file(self, file_content: bytes) -> list[bytes]:
        """
        Split file content into chunks for multipart upload.

        Args:
            file_content: Full file content as bytes

        Returns:
            List of byte chunks
        """
        chunk_size = self.settings.multipart_chunk_size_mb * 1024 * 1024
        chunks = []

        for i in range(0, len(file_content), chunk_size):
            chunks.append(file_content[i : i + chunk_size])

        return chunks if len(chunks) > 1 else [file_content]

    async def _retry_operation(
        self, operation, *args, max_retries: int = None, **kwargs
    ):
        """
        Retry an operation with exponential backoff.

        Args:
            operation: Async function to retry
            max_retries: Maximum number of retries
            *args, **kwargs: Arguments to pass to operation

        Returns:
            Result of the operation
        """
        max_retries = max_retries or self.settings.max_retries
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            except (ClientError, BotoCoreError, Exception) as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = self.settings.retry_delay_seconds * (2**attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries + 1} attempts failed")

        raise last_error

    async def upload_file_direct(
        self,
        file_content: bytes,
        key: str,
        bucket: str,
        region: str,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """
        Upload file directly to S3 using multipart upload for large files.

        Args:
            file_content: File content as bytes
            key: S3 object key
            bucket: S3 bucket name
            region: AWS region name
            content_type: Content type of the file

        Returns:
            Dict with message, key, and bucket
        """
        try:
            logger.info(
                f"Starting upload for key: {key}, bucket: {bucket}, region: {region}"
            )
            # Determine if multipart upload is needed
            chunk_size_mb = self.settings.multipart_chunk_size_mb
            file_size_mb = len(file_content) / (1024 * 1024)

            # Use multipart if file is larger than chunk size
            use_multipart = file_size_mb > chunk_size_mb

            async with await self._get_s3_client(region=region) as s3:
                if use_multipart:
                    logger.info(f"Using multipart upload for file: {key}")

                    # Initiate multipart upload
                    multipart_response = await self._retry_operation(
                        s3.create_multipart_upload,
                        Bucket=bucket,
                        Key=key,
                        ContentType=content_type,
                    )
                    upload_id = multipart_response["UploadId"]

                    try:
                        # Upload parts
                        chunks = await self._chunk_file(file_content)
                        parts = []

                        for i, chunk in enumerate(chunks, start=1):
                            part_response = await self._retry_operation(
                                self._upload_part,
                                s3,
                                bucket,
                                key,
                                upload_id,
                                i,
                                chunk,
                            )
                            parts.append(part_response)
                            logger.info(f"Uploaded part {i}/{len(chunks)}")

                        # Complete multipart upload
                        complete_response = await self._retry_operation(
                            s3.complete_multipart_upload,
                            Bucket=bucket,
                            Key=key,
                            UploadId=upload_id,
                            MultipartUpload={"Parts": parts},
                        )

                        logger.info(
                            f"Successfully uploaded file: {key} to bucket: {bucket}"
                        )
                        return {
                            "message": "File uploaded successfully using multipart upload",
                            "key": key,
                            "bucket": bucket,
                            "etag": complete_response["ETag"],
                        }
                    except Exception as e:
                        # Clean up failed multipart upload
                        logger.error(f"Multipart upload failed: {str(e)}")
                        try:
                            await s3.abort_multipart_upload(
                                Bucket=bucket,
                                Key=key,
                                UploadId=upload_id,
                            )
                        except Exception as cleanup_error:
                            logger.error(
                                f"Error cleaning up multipart upload: {str(cleanup_error)}"
                            )
                        raise
                else:
                    # Simple upload for smaller files
                    logger.info(f"Using simple upload for file: {key}")
                    await self._retry_operation(
                        s3.put_object,
                        Bucket=bucket,
                        Key=key,
                        Body=file_content,
                        ContentType=content_type,
                    )

                    logger.info(
                        f"Successfully uploaded file: {key} to bucket: {bucket}"
                    )
                    return {
                        "message": "File uploaded successfully",
                        "key": key,
                        "bucket": bucket,
                    }
        except ClientError as e:
            error_msg = f"S3 client error: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Upload failed: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    async def download_file_direct(self, key: str, bucket: str, region: str) -> bytes:
        """
        Download file directly from S3.

        Args:
            key: S3 object key
            bucket: S3 bucket name
            region: AWS region name

        Returns:
            File content as bytes
        """
        try:
            logger.info(
                f"Starting download for key: {key}, bucket: {bucket}, region: {region}"
            )
            async with await self._get_s3_client(region=region) as s3:
                response = await s3.get_object(Bucket=bucket, Key=key)
                file_content = await response["Body"].read()
                logger.info(
                    f"Successfully downloaded file: {key} from bucket: {bucket}"
                )
                return file_content
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                error_msg = f"File not found: {key}"
            else:
                error_msg = f"S3 client error: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Download failed: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    async def generate_presigned_upload_url(
        self,
        key: str,
        bucket: str,
        region: str,
        content_type: str = "application/octet-stream",
        expires_in_minutes: int = None,
    ) -> dict:
        """
        Generate presigned URL for uploading file to S3.

        Args:
            key: S3 object key
            bucket: S3 bucket name
            region: AWS region name
            content_type: Content type of the file
            expires_in_minutes: URL expiration time in minutes

        Returns:
            Dict with upload_url, key, bucket, and expires_at
        """
        try:
            logger.info(
                f"Generating presigned upload URL for key: {key}, bucket: {bucket}, region: {region}"
            )
            expires_in_minutes = (
                expires_in_minutes or self.settings.presigned_url_expiration_minutes
            )
            expires_in_seconds = expires_in_minutes * 60

            async with await self._get_s3_client(region=region) as s3:
                url = await s3.generate_presigned_url(
                    "put_object",
                    Params={
                        "Bucket": bucket,
                        "Key": key,
                        "ContentType": content_type,
                    },
                    ExpiresIn=expires_in_seconds,
                )

                expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)

                logger.info(
                    f"Successfully generated presigned upload URL for key: {key}"
                )
                return {
                    "upload_url": url,
                    "key": key,
                    "bucket": bucket,
                    "expires_at": expires_at,
                }
        except Exception as e:
            error_msg = f"Failed to generate presigned upload URL: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    async def generate_presigned_download_url(
        self, key: str, bucket: str, region: str, expires_in_minutes: int = None
    ) -> dict:
        """
        Generate presigned URL for downloading file from S3.

        Args:
            key: S3 object key
            bucket: S3 bucket name
            region: AWS region name
            expires_in_minutes: URL expiration time in minutes

        Returns:
            Dict with download_url, key, bucket, and expires_at
        """
        try:
            logger.info(
                f"Generating presigned download URL for key: {key}, bucket: {bucket}, region: {region}"
            )
            expires_in_minutes = (
                expires_in_minutes or self.settings.presigned_url_expiration_minutes
            )
            expires_in_seconds = expires_in_minutes * 60

            async with await self._get_s3_client(region=region) as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": key},
                    ExpiresIn=expires_in_seconds,
                )

                expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)

                logger.info(
                    f"Successfully generated presigned download URL for key: {key}"
                )
                return {
                    "download_url": url,
                    "key": key,
                    "bucket": bucket,
                    "expires_at": expires_at,
                }
        except Exception as e:
            error_msg = f"Failed to generate presigned download URL: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    async def check_upload_status(self, key: str, bucket: str, region: str) -> dict:
        """
        Check status of uploaded file.

        Args:
            key: S3 object key
            bucket: S3 bucket name
            region: AWS region name

        Returns:
            Dict with key, exists, size, last_modified, and etag
        """
        try:
            logger.info(
                f"Checking upload status for key: {key}, bucket: {bucket}, region: {region}"
            )
            async with await self._get_s3_client(region=region) as s3:
                response = await s3.head_object(Bucket=bucket, Key=key)

                return {
                    "key": key,
                    "exists": True,
                    "size": response.get("ContentLength"),
                    "last_modified": response.get("LastModified"),
                    "etag": response.get("ETag", "").strip('"'),
                }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                return {
                    "key": key,
                    "exists": False,
                    "size": None,
                    "last_modified": None,
                    "etag": None,
                }
            else:
                error_msg = f"Failed to check upload status: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Failed to check upload status: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    async def delete_file(self, key: str, bucket: str, region: str) -> dict:
        """
        Delete file from S3.

        Args:
            key: S3 object key
            bucket: S3 bucket name
            region: AWS region name

        Returns:
            Dict with message, key, bucket, and deleted boolean
        """
        try:
            logger.info(
                f"Starting deletion for key: {key}, bucket: {bucket}, region: {region}"
            )
            async with await self._get_s3_client(region=region) as s3:
                # Check if file exists before attempting deletion
                try:
                    await s3.head_object(Bucket=bucket, Key=key)
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code == "404":
                        logger.warning(f"File does not exist: {key}")
                        return {
                            "message": "Failed: File does not exist",
                            "key": key,
                            "bucket": bucket,
                            "deleted": False,
                        }
                    else:
                        error_msg = f"Failed to check file existence: {str(e)}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)

                # File exists, proceed with deletion
                await self._retry_operation(
                    s3.delete_object,
                    Bucket=bucket,
                    Key=key,
                )

                logger.info(
                    f"Successfully deleted file: {key} from bucket: {bucket}"
                )
                return {
                    "message": "File deleted successfully",
                    "key": key,
                    "bucket": bucket,
                    "deleted": True,
                }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                error_msg = f"File not found: {key}"
                logger.warning(error_msg)
                return {
                    "message": error_msg,
                    "key": key,
                    "bucket": bucket,
                    "deleted": False,
                }
            else:
                error_msg = f"S3 client error: {str(e)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Delete failed: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
