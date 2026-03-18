"""AWS S3 abstraction: upload, download, presign (Section 7)."""

from __future__ import annotations

import io
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.exceptions import StorageDownloadError, StorageUploadError

# Presigned URL expiry (seconds)
PRESIGN_EXPIRY = 900  # 15 minutes


def _get_client() -> object:
    settings = get_settings()
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )


def upload_bytes(
    key: str,
    body: bytes | BinaryIO,
    content_type: str | None = None,
) -> None:
    """Upload bytes or file-like to S3. Raises StorageUploadError on failure."""
    settings = get_settings()
    client = _get_client()
    try:
        extra = {}
        if content_type:
            extra["ContentType"] = content_type
        client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=body,
            **extra,
        )
    except ClientError as e:
        raise StorageUploadError(key, str(e)) from e


def download_bytes(s3_key: str) -> bytes:
    """Download object from S3. Raises StorageDownloadError on failure."""
    settings = get_settings()
    client = _get_client()
    try:
        response = client.get_object(Bucket=settings.S3_BUCKET, Key=s3_key)
        return response["Body"].read()
    except ClientError as e:
        raise StorageDownloadError(s3_key, str(e)) from e


def presign_get_url(s3_key: str, expiry: int = PRESIGN_EXPIRY) -> str:
    """Generate presigned GET URL for download."""
    settings = get_settings()
    client = _get_client()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
            ExpiresIn=expiry,
        )
        return url
    except ClientError as e:
        raise StorageDownloadError(s3_key, str(e)) from e


def build_key(user_id: str, content_hash: str, ext: str) -> str:
    """Build S3 key: uploads/{user_id}/{content_hash}.{ext}."""
    return f"uploads/{user_id}/{content_hash}.{ext}"
