from __future__ import annotations

import time
from collections import deque
from threading import Lock

from fastapi import HTTPException

_buckets: dict[str, deque[float]] = {}
_lock = Lock()


def check_rate_limit(ip: str, max_requests: int = 5, window: int = 900) -> None:
    now = time.monotonic()
    with _lock:
        dq = _buckets.setdefault(ip, deque())
        cutoff = now - window
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Try again later.",
            )
        dq.append(now)
