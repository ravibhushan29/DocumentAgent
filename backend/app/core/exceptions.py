"""Typed domain exceptions. All map to HTTP responses via global handler (Section 17)."""

from __future__ import annotations

from typing import Any


class DocAgentError(Exception):
    """Base for all domain exceptions. Subclasses define HTTP status and error code."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, **details: Any) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


# ── 4xx ───────────────────────────────────────────────────────────────────


class UnsupportedFileTypeError(DocAgentError):
    status_code = 400
    error_code = "UNSUPPORTED_FILE_TYPE"

    def __init__(self, file_type: str) -> None:
        super().__init__(f"Unsupported file type: {file_type}", file_type=file_type)


class FileTooLargeError(DocAgentError):
    status_code = 413
    error_code = "FILE_TOO_LARGE"

    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(
            f"File size {size} exceeds maximum {max_size} bytes",
            size=size,
            max_size=max_size,
        )


class DuplicateDocumentError(DocAgentError):
    status_code = 409
    error_code = "DUPLICATE_DOCUMENT"

    def __init__(self, document_id: str) -> None:
        super().__init__(f"Document already exists: {document_id}", document_id=document_id)


class DocumentNotFoundError(DocAgentError):
    status_code = 404
    error_code = "DOCUMENT_NOT_FOUND"

    def __init__(self, document_id: str) -> None:
        super().__init__(f"Document not found: {document_id}", document_id=document_id)


class DocumentNotIndexedError(DocAgentError):
    status_code = 422
    error_code = "DOCUMENT_NOT_INDEXED"

    def __init__(self, document_id: str, status: str) -> None:
        super().__init__(
            f"Document not indexed (status={status})",
            document_id=document_id,
            status=status,
        )


class AuthenticationError(DocAgentError):
    status_code = 401
    error_code = "AUTHENTICATION_ERROR"

    def __init__(self, message: str = "Invalid or expired token") -> None:
        super().__init__(message)


class AuthorizationError(DocAgentError):
    status_code = 403
    error_code = "AUTHORIZATION_ERROR"

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message)


class RateLimitError(DocAgentError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message)


# ── 5xx (retried by worker or reported) ───────────────────────────────────


class StorageUploadError(DocAgentError):
    status_code = 500
    error_code = "STORAGE_UPLOAD_ERROR"

    def __init__(self, s3_key: str, reason: str) -> None:
        super().__init__(f"Upload failed: {reason}", s3_key=s3_key, reason=reason)


class StorageDownloadError(DocAgentError):
    status_code = 500
    error_code = "STORAGE_DOWNLOAD_ERROR"

    def __init__(self, s3_key: str, reason: str) -> None:
        super().__init__(f"Download failed: {reason}", s3_key=s3_key, reason=reason)


class EmbeddingError(DocAgentError):
    status_code = 500
    error_code = "EMBEDDING_ERROR"

    def __init__(self, reason: str) -> None:
        super().__init__(f"Embedding failed: {reason}", reason=reason)


class QueuePublishError(DocAgentError):
    status_code = 500
    error_code = "QUEUE_PUBLISH_ERROR"

    def __init__(self, reason: str) -> None:
        super().__init__(f"Queue publish failed: {reason}", reason=reason)


class ParseError(DocAgentError):
    status_code = 500
    error_code = "PARSE_ERROR"

    def __init__(self, file_type: str, reason: str) -> None:
        super().__init__(f"Parse failed: {reason}", file_type=file_type, reason=reason)
