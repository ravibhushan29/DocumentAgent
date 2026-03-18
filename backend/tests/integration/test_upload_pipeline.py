"""Integration test: upload → ingest → verify chunks in DB (Section 18).

Requires: PostgreSQL with migrations, Redis (optional for Celery), S3/MinIO (or mock).
Run with pytest -k test_upload_pipeline (or full integration with testcontainers).
"""

import pytest

# Placeholder: full test would use testcontainers for DB, moto for S3,
# and either run pipeline in-process or mock Kafka/Celery
@pytest.mark.skip(reason="Requires DB + S3/Kafka or mocks; run manually with real stack")
def test_upload_and_ingest_e2e() -> None:
    """Upload a small PDF, run pipeline, assert chunks in document_chunks."""
    pass
