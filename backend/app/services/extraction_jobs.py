"""Durable extraction queue primitives shared by the API and the worker."""

import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.extraction_job import ExtractionJob, ExtractionJobState
from backend.app.models.receipt import Receipt
from backend.app.services.receipt_review import store_extraction


def durable_upload(organization_id: UUID, filename: str, payload: bytes) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    suffix = Path(filename).suffix.lower()[:10] or ".bin"
    directory = Path(settings.upload_root) / str(organization_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}{suffix}"
    if not path.exists():
        path.write_bytes(payload)
    return str(path)


def create_job(db: Session, organization_id: UUID, receipt: Receipt, path: str, key: str) -> ExtractionJob:
    existing = db.scalar(select(ExtractionJob).where(ExtractionJob.organization_id == organization_id, ExtractionJob.idempotency_key == key))
    if existing:
        return existing
    job = ExtractionJob(organization_id=organization_id, receipt_id=receipt.id, storage_path=path, idempotency_key=key, state=ExtractionJobState.QUEUED, worker_version=settings.worker_version)
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(ExtractionJob).where(ExtractionJob.organization_id == organization_id, ExtractionJob.idempotency_key == key))
        if existing is None:
            raise
        return existing
    db.refresh(job)
    return job


def claim_next(db: Session) -> ExtractionJob | None:
    now = datetime.now(UTC)
    candidate = db.scalar(select(ExtractionJob).where(
        ExtractionJob.state.in_([ExtractionJobState.QUEUED, ExtractionJobState.RETRYABLE_FAILED]),
        (ExtractionJob.next_attempt_at.is_(None) | (ExtractionJob.next_attempt_at <= now)),
        (ExtractionJob.lease_until.is_(None) | (ExtractionJob.lease_until < now)),
    ).order_by(ExtractionJob.created_at).with_for_update(skip_locked=True))
    if candidate is None:
        return None
    candidate.state = ExtractionJobState.PROCESSING
    candidate.lease_until = now + timedelta(seconds=settings.extraction_lease_seconds)
    candidate.updated_at = now
    db.commit()
    db.refresh(candidate)
    return candidate


def process_job(db: Session, job_id: UUID) -> ExtractionJob:
    job = db.get(ExtractionJob, job_id)
    if job is None:
        raise ValueError("job not found")
    receipt = db.scalar(select(Receipt).where(Receipt.id == job.receipt_id, Receipt.organization_id == job.organization_id))
    if receipt is None:
        return fail_job(db, job, "tenant_record_missing", "receipt is unavailable")
    try:
        if os.environ.get("FINFLOW_MOCK_EXTRACTION", "").lower() in {"1", "true", "yes"}:
            prediction = {"company": "Mock Cafe", "date": "2025-01-15", "address": "1 Demo Road", "total": "12.50", "currency": "USD"}
        else:
            from ml.inference.predict import predict_image
            _, _, prediction, parsing_error = predict_image(job.storage_path, settings.model_id, settings.adapter_path)
            if prediction is None:
                raise ValueError(parsing_error or "model output could not be parsed")
        receipt.extracted_data = prediction
        receipt.company = prediction.get("company")
        receipt.receipt_date = datetime.fromisoformat(prediction["date"]).date() if prediction.get("date") else None
        receipt.address = prediction.get("address")
        receipt.total = prediction.get("total")
        receipt.currency = prediction.get("currency")
        store_extraction(db, receipt)
        job.state = ExtractionJobState.COMPLETED
        job.lease_until = None
        job.error_code = job.error_message = None
        db.commit()
        return job
    except Exception as exc:
        db.rollback()
        return fail_job(db, job, "extraction_failed", str(exc)[:500])


def fail_job(db: Session, job: ExtractionJob, code: str, message: str) -> ExtractionJob:
    job.retry_count += 1
    terminal = job.retry_count >= settings.extraction_max_retries
    job.state = ExtractionJobState.TERMINAL_FAILED if terminal else ExtractionJobState.RETRYABLE_FAILED
    job.error_code, job.error_message = code, message
    job.lease_until = None
    job.next_attempt_at = None if terminal else datetime.now(UTC) + timedelta(seconds=2 ** job.retry_count)
    receipt = db.get(Receipt, job.receipt_id)
    if receipt and terminal:
        receipt.status = "failed"
    db.commit()
    db.refresh(job)
    return job


def reclaim_stale(db: Session) -> int:
    now = datetime.now(UTC)
    result = db.execute(update(ExtractionJob).where(ExtractionJob.state == ExtractionJobState.PROCESSING, ExtractionJob.lease_until < now).values(state=ExtractionJobState.RETRYABLE_FAILED, next_attempt_at=now, lease_until=None, updated_at=now))
    db.commit()
    return result.rowcount or 0
