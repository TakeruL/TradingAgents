"""Vendor JSON responses kept on disk under the data cache directory.

A response is read back while it is younger than its time to live; ``math.inf``
keeps it for good, for data that cannot change once published (a closed
trading day). A failed fetch raises and caches nothing, so the next call asks
again.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.files import replace_file


def cache_path(namespace: str, key: str) -> Path:
    """Where the response for ``key`` is kept. Hashed, so a key never forms a path."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return Path(get_config()["data_cache_dir"]) / namespace / f"{digest}.json"


def cached_json(namespace: str, key: str, ttl_seconds: float | None, fetch: Callable[[], Any]) -> Any:
    """``fetch()``'s result, from disk while younger than ``ttl_seconds``.

    ``None`` or a non-positive TTL bypasses the cache entirely.
    """
    if not ttl_seconds or ttl_seconds <= 0:
        return fetch()
    path = cache_path(namespace, key)
    if path.exists() and (ttl_seconds == math.inf or time.time() - path.stat().st_mtime < ttl_seconds):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            pass  # a truncated file is a miss, not a failure
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    replace_file(
        path,
        lambda temp: Path(temp).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"),
    )
    return data
