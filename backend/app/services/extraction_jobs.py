"""Durable extraction queue primitives shared by the API and the worker."""

import hashlib
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.observability import elapsed_seconds, job_log
from backend.app.models.extraction_job import ExtractionJob, ExtractionJobState
from backend.app.models.receipt import Receipt
from backend.app.services.audit import record_event
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


def adapter_fingerprint(path: str) -> str | None:
    if not path or not Path(path).is_dir():
        return None
    digest = hashlib.sha256()
    for item in sorted(Path(path).glob("adapter_*")):
        if item.is_file():
            digest.update(item.name.encode())
            digest.update(item.read_bytes())
    return digest.hexdigest() if digest.digest_size else None


def create_job(db: Session, organization_id: UUID, receipt: Receipt, path: str, key: str, payload_hash: str) -> ExtractionJob:
    existing = db.scalar(select(ExtractionJob).where(ExtractionJob.organization_id == organization_id, ExtractionJob.idempotency_key == key))
    if existing:
        if existing.payload_hash != payload_hash:
            raise ValueError("Idempotency-Key was already used for different content") from None
        return existing
    job = ExtractionJob(organization_id=organization_id, receipt_id=receipt.id, storage_path=path, idempotency_key=key, payload_hash=payload_hash, state=ExtractionJobState.QUEUED, worker_version=settings.worker_version)
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(ExtractionJob).where(ExtractionJob.organization_id == organization_id, ExtractionJob.idempotency_key == key))
        if existing is None:
            raise
        if existing.payload_hash != payload_hash:
            raise ValueError("Idempotency-Key was already used for different content") from None
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
    candidate.lease_owner = uuid4().hex
    candidate.fence += 1
    candidate.lease_until = now + timedelta(seconds=settings.extraction_lease_seconds)
    candidate.updated_at = now
    db.commit()
    db.refresh(candidate)
    job_log("job.processing", job_id=candidate.id, organization_id=candidate.organization_id, fence=candidate.fence)
    return candidate


def process_job(db: Session, job_id: UUID, lease_owner: str | None = None, fence: int | None = None) -> ExtractionJob:
    job = db.get(ExtractionJob, job_id)
    if job is None:
        raise ValueError("job not found")
    if job.state in {ExtractionJobState.COMPLETED, ExtractionJobState.TERMINAL_FAILED}:
        return job
    lease_owner = lease_owner or job.lease_owner
    fence = fence if fence is not None else job.fence
    if job.state != ExtractionJobState.PROCESSING or not lease_owner:
        raise ValueError("job is not owned by a processing lease")
    receipt = db.scalar(select(Receipt).where(Receipt.id == job.receipt_id, Receipt.organization_id == job.organization_id))
    if receipt is None:
        return fail_job(db, job, "tenant_record_missing", "receipt is unavailable")
    if receipt.status in {"approved", "rejected"}:
        job.state = ExtractionJobState.TERMINAL_FAILED
        job.error_code = "receipt_terminal"
        job.error_message = "receipt was finalized before this job ran"
        job.lease_owner = None
        job.lease_until = None
        db.commit()
        return job
    try:
        started = time.monotonic()
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
        updated = db.query(ExtractionJob).filter(ExtractionJob.id == job.id, ExtractionJob.state == ExtractionJobState.PROCESSING, ExtractionJob.lease_owner == lease_owner, ExtractionJob.fence == fence).update({"state": ExtractionJobState.COMPLETED, "lease_until": None, "lease_owner": None, "error_code": None, "error_message": None}, synchronize_session=False)
        if updated != 1:
            db.rollback()
            return db.get(ExtractionJob, job.id)
        store_extraction(db, receipt, commit=False)
        job.model_id = settings.model_id
        job.model_revision = settings.model_revision or None
        job.adapter_fingerprint = adapter_fingerprint(settings.adapter_path)
        record_event(db, job.organization_id, "extraction.completed", "extraction_job", job.id, correlation_id=str(job.id), details={"latency_seconds": elapsed_seconds(started)}, model_id=job.model_id, model_revision=job.model_revision, adapter_fingerprint=job.adapter_fingerprint)
        job_log("job.completed", job_id=job.id, latency_seconds=elapsed_seconds(started))
        db.commit()
        return job
    except Exception as exc:
        db.rollback()
        return fail_job(db, job, "extraction_failed", str(exc)[:500], lease_owner, fence)


def renew_lease(db: Session, job_id: UUID, lease_owner: str, fence: int) -> bool:
    """Extend only the currently fenced lease; stale workers cannot renew it."""
    now = datetime.now(UTC)
    updated = db.query(ExtractionJob).filter(
        ExtractionJob.id == job_id,
        ExtractionJob.state == ExtractionJobState.PROCESSING,
        ExtractionJob.lease_owner == lease_owner,
        ExtractionJob.fence == fence,
    ).update({"lease_until": now + timedelta(seconds=settings.extraction_lease_seconds), "updated_at": now}, synchronize_session=False)
    db.commit()
    return updated == 1


def fail_job(db: Session, job: ExtractionJob, code: str, message: str, lease_owner: str | None = None, fence: int | None = None) -> ExtractionJob:
    lease_owner = lease_owner or job.lease_owner
    fence = fence if fence is not None else job.fence
    current = db.get(ExtractionJob, job.id)
    if current is None or current.state != ExtractionJobState.PROCESSING or current.lease_owner != lease_owner or current.fence != fence:
        return current or job
    retry_count = current.retry_count + 1
    terminal = retry_count >= settings.extraction_max_retries
    current.retry_count = retry_count
    current.state = ExtractionJobState.TERMINAL_FAILED if terminal else ExtractionJobState.RETRYABLE_FAILED
    current.error_code, current.error_message = code, message
    current.lease_until = None
    current.lease_owner = None
    current.next_attempt_at = None if terminal else datetime.now(UTC) + timedelta(seconds=2 ** retry_count)
    receipt = db.get(Receipt, current.receipt_id)
    if receipt and terminal and receipt.status not in {"approved", "rejected"}:
        receipt.status = "failed"
    record_event(db, current.organization_id, "extraction.failed", "extraction_job", current.id, correlation_id=str(current.id), details={"error_code": code, "retry_count": retry_count})
    job_log("job.failed", job_id=current.id, retry_count=retry_count, terminal=terminal)
    db.commit()
    db.refresh(current)
    return current


def reclaim_stale(db: Session) -> int:
    now = datetime.now(UTC)
    result = db.execute(update(ExtractionJob).where(ExtractionJob.state == ExtractionJobState.PROCESSING, ExtractionJob.lease_until < now).values(state=ExtractionJobState.RETRYABLE_FAILED, next_attempt_at=now, lease_until=None, updated_at=now))
    db.commit()
    return result.rowcount or 0
