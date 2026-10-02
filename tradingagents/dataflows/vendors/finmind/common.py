"""FinMind API client.

One endpoint serves every dataset: ``GET /api/v4/data?dataset=...&data_id=...``.
A token is optional. Without one FinMind allows a few hundred requests an hour
per IP, and a free registered token roughly doubles that; set it in
``FINMIND_API_TOKEN``. The token travels in the Authorization header, never in
the URL, so it cannot surface in an error message or a log.

Running out of quota is routine on the free tier, so it is not an error the run
should die on: the client raises ``VendorUnavailableError`` and the router moves
on to the next configured vendor (the official TWSE/TPEx data). Once FinMind has
said the quota is spent, it is skipped for a cool-down period instead of being
asked again on every tool call.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

import requests

from tradingagents.dataflows.errors import VendorNotConfiguredError, VendorUnavailableError
from tradingagents.dataflows.json_cache import cached_json

logger = logging.getLogger(__name__)

API_URL = "https://api.finmindtrade.com/api/v4/data"
REQUEST_TIMEOUT = 30

# How long FinMind is skipped after it reports the quota spent. Its quota is
# counted per hour, so asking again sooner mostly wastes a request.
RATE_LIMIT_COOLDOWN_SECONDS = 600

_RATE_LIMIT_STATUSES = (402, 429)

_lock = threading.Lock()
_skip_until = 0.0  # time.monotonic() before which FinMind is not asked


def _token() -> str:
    return os.getenv("FINMIND_API_TOKEN", "").strip()


def _check_cooldown() -> None:
    with _lock:
        remaining = _skip_until - time.monotonic()
    if remaining > 0:
        raise VendorUnavailableError(
            f"FinMind request quota was reached; skipping FinMind for another {int(remaining)}s"
        )


def _start_cooldown() -> None:
    global _skip_until
    with _lock:
        _skip_until = time.monotonic() + RATE_LIMIT_COOLDOWN_SECONDS


def reset_cooldown() -> None:
    """Forget a spent quota, e.g. after setting a token mid-process."""
    global _skip_until
    with _lock:
        _skip_until = 0.0


def _request(params: dict) -> list[dict]:
    _check_cooldown()
    token = _token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    dataset = params.get("dataset")
    try:
        response = requests.get(API_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        raise VendorUnavailableError(f"FinMind request failed ({type(exc).__name__})") from exc

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    status = payload.get("status", response.status_code) if isinstance(payload, dict) else response.status_code
    message = str(payload.get("msg", "")).strip() if isinstance(payload, dict) else ""

    if response.status_code in _RATE_LIMIT_STATUSES or status in _RATE_LIMIT_STATUSES:
        _start_cooldown()
        hint = "" if token else "; set FINMIND_API_TOKEN for a higher quota"
        logger.warning("FinMind quota reached (%s); skipping it for %ss", message, RATE_LIMIT_COOLDOWN_SECONDS)
        raise VendorUnavailableError(f"FinMind request quota reached ({message or status}){hint}")
    if response.status_code in (401, 403) or status in (401, 403):
        raise VendorNotConfiguredError(f"FinMind refused the token ({message or status}); check FINMIND_API_TOKEN")
    if response.status_code == 400 and "level" in message.lower():
        # Sponsor-only datasets answer 400 with a message about the user level.
        raise VendorNotConfiguredError(f"FinMind dataset {dataset} needs a higher membership level: {message}")
    if response.status_code != 200 or status != 200 or not isinstance(payload, dict):
        raise VendorUnavailableError(f"FinMind returned {status} for {dataset}: {message or 'unreadable response'}")

    data = payload.get("data") or []
    if not isinstance(data, list):
        raise VendorUnavailableError(f"FinMind returned an unexpected payload for {dataset}")
    return data


def fetch_dataset(
    dataset: str,
    *,
    data_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    ttl_seconds: float | None = None,
) -> list[dict[str, Any]]:
    """Rows of one FinMind dataset, optionally for one ``data_id`` and date range.

    An empty list means FinMind answered and has no rows; callers decide whether
    that is "no data". ``ttl_seconds`` caches the answer on disk (``math.inf``
    for ranges that can no longer change).
    """
    params = {"dataset": dataset}
    if data_id:
        params["data_id"] = data_id
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    key = json.dumps(params, sort_keys=True)
    return cached_json("finmind", key, ttl_seconds, lambda: _request(params))
