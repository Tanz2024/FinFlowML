import json
import logging
import time
from collections import Counter

logger = logging.getLogger("finflowml.jobs")
metrics = Counter()


def job_log(action: str, **fields) -> None:
    metrics[action] += 1
    logger.info(json.dumps({"action": action, **fields}, default=str, sort_keys=True))


def elapsed_seconds(start: float) -> float:
    return round(time.monotonic() - start, 4)
