"""Simple in-memory rate limiter."""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

_lock = Lock()
_hits: dict[str, list[float]] = defaultdict(list)


def allow(key: str, limit: int = 30, window: int = 60) -> bool:
    now = time.time()
    with _lock:
        arr = _hits[key]
        _hits[key] = [t for t in arr if now - t < window]
        if len(_hits[key]) >= limit:
            return False
        _hits[key].append(now)
        return True
