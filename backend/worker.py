"""Run with `python -m backend.worker`; one durable job at a time per process."""

import time

from backend.app.database.session import SessionLocal
from backend.app.services.extraction_jobs import claim_next, process_job, reclaim_stale


def run_forever() -> None:
    while True:
        with SessionLocal() as db:
            reclaim_stale(db)
            job = claim_next(db)
            if job:
                process_job(db, job.id)
                continue
        time.sleep(1)


if __name__ == "__main__":
    run_forever()
