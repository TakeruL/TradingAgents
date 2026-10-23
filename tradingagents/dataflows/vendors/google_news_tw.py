"""Taiwan financial headlines from Google News (Traditional Chinese edition).

Google News' RSS search aggregates Taiwan's financial press (經濟日報, 工商時報,
鉅亨網, 自由財經, Yahoo 股市 …) under one query. ``after:`` / ``before:``
operators bound the search to a date range, so a historical run reads the
headlines of its own window. No key. Returns a formatted plaintext block and
never raises.
"""

from __future__ import annotations

import logging
import math
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.date_window import in_window
from tradingagents.dataflows.errors import VendorUnavailableError
from tradingagents.dataflows.json_cache import cached_json
from tradingagents.dataflows.tw_common import ttl_for
from tradingagents.dataflows.vendors.yahoo.news import get_global_news_yfinance

logger = logging.getLogger(__name__)

FEED_URL = "https://news.google.com/rss/search"
TIMEOUT = 15
EDITION = {"hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"}
RETRY_DELAY = 3
# Google answers a quick burst of searches with 503s, so requests from every
# thread are spaced this far apart.
MIN_INTERVAL = 1.0
_lock = threading.Lock()
_next_slot = 0.0


def _wait_turn() -> None:
    global _next_slot
    with _lock:
        now = time.monotonic()
        wait = max(0.0, _next_slot - now)
        _next_slot = max(now, _next_slot) + MIN_INTERVAL
    if wait:
        time.sleep(wait)


class _FeedUnreadable(Exception):
    pass


def _read_feed(query: str, start_date: str, end_date: str) -> list[list[str]]:
    after = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    params = {"q": f"{query} after:{start_date} before:{after}", **EDITION}
    for attempt in range(2):  # Google answers an occasional burst with a 503
        _wait_turn()
        try:
            response = requests.get(FEED_URL, params=params, timeout=TIMEOUT,
                                    headers={"User-Agent": "Mozilla/5.0 (compatible; TradingAgents)"})
            response.raise_for_status()
            items = ET.fromstring(response.content).findall(".//item")
            break
        except (requests.RequestException, ET.ParseError) as exc:
            if attempt:
                logger.warning("Google News fetch failed for %s: %s", query, exc)
                raise _FeedUnreadable from exc
            time.sleep(RETRY_DELAY)
    return [[item.findtext("pubDate") or "", (item.findtext("title") or "").strip(),
             (item.findtext("source") or "").strip()] for item in items]


def search_google_news_tw(query: str, *, start_date: str, end_date: str) -> list[tuple] | None:
    """``(published, title, source)`` for headlines within the window, newest
    first and without duplicates; None if the feed could not be read.

    A window that has closed is kept on disk for good, an open one for an hour.
    """
    try:
        items = cached_json("google_news_tw", f"{query}|{start_date}|{end_date}", ttl_for(end_date),
                            lambda: _read_feed(query, start_date, end_date))
    except _FeedUnreadable:
        return None

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    seen, articles = set(), []
    for pub_date, title, source in items:
        try:
            published = parsedate_to_datetime(pub_date)
        except (TypeError, ValueError):
            published = None
        if published is None or not in_window(published, start_dt, end_dt):
            continue
        # Titles end with " - <publisher>", which the source field already gives.
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].strip()
        if not title or title in seen:
            continue
        seen.add(title)
        articles.append((published, title, source))
    articles.sort(reverse=True)
    return articles


def _line(article: tuple) -> str:
    published, title, source = article
    return f"  [{published:%Y-%m-%d}] {title} (source: {source or 'unknown'})"


def fetch_google_news_tw(query: str, *, start_date: str, end_date: str, limit: int = 15) -> str:
    """Headlines matching ``query`` published within ``[start_date, end_date]``, newest first."""
    articles = search_google_news_tw(query, start_date=start_date, end_date=end_date)
    if articles is None:
        return "<Google News unavailable: the feed could not be read; this is not an absence of news>"
    if not articles:
        return f"<no Google News articles about {query} within {start_date}..{end_date}>"
    lines = [f"Google News (zh-TW) — {min(len(articles), limit)} of {len(articles)} headlines about "
             f"{query} within {start_date}..{end_date}:"]
    lines += [_line(a) for a in articles[:limit]]
    return "\n".join(lines)


def get_global_news_tw(as_of_date: str, look_back_days: int | None = None, limit: int | None = None) -> str:
    """Taiwan macro headlines (Google News, Taiwan edition) ahead of the international ones.

    Runs each of ``tw_global_news_queries`` and keeps a few headlines per topic,
    so no one busy topic fills the list; then appends the international
    headlines the yfinance vendor returns for ``global_news_queries``. Serves
    the Taiwan section only in the Taiwan market mode; otherwise it is the
    yfinance answer alone.
    """
    config = get_config()
    if config.get("market") != "tw":
        return get_global_news_yfinance(as_of_date, look_back_days, limit)
    if look_back_days is None:
        look_back_days = config["global_news_lookback_days"]
    if limit is None:
        limit = config["global_news_article_limit"]
    queries = config.get("tw_global_news_queries") or []
    end_dt = datetime.strptime(as_of_date, "%Y-%m-%d")
    start_date = (end_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")

    total = config.get("tw_global_news_article_limit") or limit
    per_query = max(2, math.ceil(total / max(len(queries), 1)))
    seen, picked, failed = set(), [], 0
    for query in queries:
        found = search_google_news_tw(query, start_date=start_date, end_date=as_of_date)
        if found is None:
            failed += 1
            continue
        fresh = [a for a in found if a[1] not in seen][:per_query]
        seen.update(a[1] for a in fresh)
        picked += [(query, a) for a in fresh]
    if queries and failed == len(queries):
        raise VendorUnavailableError("Google News could not be read for any Taiwan macro query")

    lines = [f"## Taiwan macro news (Google News, Taiwan edition, Traditional Chinese), "
             f"{start_date} to {as_of_date}"]
    for query in queries:
        rows = [a for q, a in picked if q == query]
        if rows:
            lines.append(f"### {query}")
            lines += [_line(a) for a in rows]
    if len(lines) == 1:
        lines.append(f"<no Taiwan macro headlines within {start_date}..{as_of_date}>")
    if failed:
        lines.append(f"<{failed} of {len(queries)} topics could not be read; this is not an absence of news>")

    try:
        international = get_global_news_yfinance(as_of_date, look_back_days, limit)
    except Exception as exc:  # the Taiwan section stands on its own
        logger.warning("International news unavailable: %s", exc)
        international = "<international headlines unavailable; this is not an absence of news>"
    return "\n".join(lines) + "\n\n## International news (Yahoo Finance)\n\n" + international
