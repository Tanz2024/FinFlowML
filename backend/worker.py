"""Run with `python -m backend.worker`; one durable job at a time per process."""

import time
from threading import Event, Thread

from backend.app.core.config import settings
from backend.app.database import base as _model_registry  # noqa: F401
from backend.app.database.session import SessionLocal
from backend.app.services.extraction_jobs import claim_next, process_job, reclaim_stale, renew_lease


def _heartbeat(job_id, lease_owner, fence, stop: Event) -> None:
    while not stop.wait(max(1, settings.extraction_lease_seconds // 3)):
        with SessionLocal() as heartbeat_db:
            if not renew_lease(heartbeat_db, job_id, lease_owner, fence):
                return


def run_forever() -> None:
    while True:
        with SessionLocal() as db:
            reclaim_stale(db)
            job = claim_next(db)
            if job:
                stop = Event()

                thread = Thread(target=_heartbeat, args=(job.id, job.lease_owner, job.fence, stop), name=f"lease-{job.id}", daemon=True)
                thread.start()
                try:
                    process_job(db, job.id, job.lease_owner, job.fence)
                finally:
                    stop.set()
                    thread.join(timeout=2)
                continue
        time.sleep(1)


if __name__ == "__main__":
    run_forever()
