"""HTTP access to the official TWSE and TPEx open data.

Both exchanges serve JSON without a key, but they guard it:

- TWSE resets connections that carry no browser-style User-Agent, and answers a
  client that asks too fast (or from a network it distrusts) with an HTML page
  reading "FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED" and status 200.
  That page is an outage, not data, so it raises ``VendorUnavailableError``.
- Requests are spaced per host, across threads (the analysts run side by side),
  because a burst is what gets an address blocked.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

import requests

from tradingagents import __version__
from tradingagents.dataflows.errors import VendorUnavailableError
from tradingagents.dataflows.json_cache import cached_json

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
USER_AGENT = f"Mozilla/5.0 (compatible; TradingAgents/{__version__})"

# Minimum spacing between two requests to the same host.
MIN_INTERVAL_SECONDS = 2.0

# How long a host that answered with its security page is left alone. Asking
# again at once only prolongs the block.
BLOCKED_COOLDOWN_SECONDS = 300

_SECURITY_PAGE_MARKERS = ("FOR SECURITY REASONS", "因為安全性考量")

_lock = threading.Lock()
_next_slot: dict[str, float] = {}
_blocked_until: dict[str, float] = {}


def _wait_turn(host: str) -> None:
    """Reserve the next free slot for ``host`` and sleep until it comes.

    The slot is reserved under the lock and slept outside it, so concurrent
    callers queue up at the right spacing without holding each other's lock.
    """
    with _lock:
        now = time.monotonic()
        slot = max(now, _next_slot.get(host, 0.0))
        _next_slot[host] = slot + MIN_INTERVAL_SECONDS
    if slot > now:
        time.sleep(slot - now)


def _check_blocked(host: str) -> None:
    with _lock:
        remaining = _blocked_until.get(host, 0.0) - time.monotonic()
    if remaining > 0:
        raise VendorUnavailableError(f"{host} blocked recent requests; leaving it alone for another {int(remaining)}s")


def _mark_blocked(host: str) -> None:
    with _lock:
        _blocked_until[host] = time.monotonic() + BLOCKED_COOLDOWN_SECONDS


def _get(url: str, params: dict | None) -> requests.Response:
    return requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT,
    )


def fetch_json(url: str, params: dict | None = None) -> Any:
    """GET ``url`` and return its JSON, with every failure as ``VendorUnavailableError``.

    A dropped connection or a timeout is tried once more, at the host's spacing:
    both exchanges drop the odd request under load.
    """
    host = urlsplit(url).hostname or url
    _check_blocked(host)
    for attempt in (1, 2):
        _wait_turn(host)
        try:
            response = _get(url, params)
            response.raise_for_status()
            break
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt == 2:
                raise VendorUnavailableError(f"{host} request failed ({type(exc).__name__})") from exc
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            raise VendorUnavailableError(f"{host} request failed ({status or type(exc).__name__})") from exc

    text = response.text
    if any(marker in text[:2000] for marker in _SECURITY_PAGE_MARKERS):
        logger.warning("%s answered with its security block page; leaving it alone for %ss",
                       host, BLOCKED_COOLDOWN_SECONDS)
        _mark_blocked(host)
        raise VendorUnavailableError(
            f"{host} refused the request with its security page (too many requests, "
            "or a network it blocks); try again later"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise VendorUnavailableError(f"{host} returned a response that is not JSON") from exc


def cached_fetch_json(url: str, params: dict | None = None, *, ttl_seconds: float | None = None) -> Any:
    """``fetch_json`` through the on-disk cache."""
    key = url if not params else f"{url}?{urlencode(sorted(params.items()))}"
    return cached_json("twse", key, ttl_seconds, lambda: fetch_json(url, params))
