"""Taiwan financial headlines from Google News (Traditional Chinese edition).

Google News' RSS search aggregates Taiwan's financial press (經濟日報, 工商時報,
鉅亨網, 自由財經, Yahoo 股市 …) under one query. ``after:`` / ``before:``
operators bound the search to a date range, so a historical run reads the
headlines of its own window. No key. Returns a formatted plaintext block and
never raises.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests

from tradingagents.dataflows.date_window import in_window

logger = logging.getLogger(__name__)

FEED_URL = "https://news.google.com/rss/search"
TIMEOUT = 15
EDITION = {"hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"}


def fetch_google_news_tw(query: str, *, start_date: str, end_date: str, limit: int = 15) -> str:
    """Headlines matching ``query`` published within ``[start_date, end_date]``, newest first."""
    after = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    params = {"q": f"{query} after:{start_date} before:{after}", **EDITION}
    try:
        response = requests.get(FEED_URL, params=params, timeout=TIMEOUT,
                                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingAgents)"})
        response.raise_for_status()
        items = ET.fromstring(response.content).findall(".//item")
    except (requests.RequestException, ET.ParseError) as exc:
        logger.warning("Google News fetch failed for %s: %s", query, exc)
        return "<Google News unavailable: the feed could not be read; this is not an absence of news>"

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    seen, articles = set(), []
    for item in items:
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
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
    if not articles:
        return f"<no Google News articles about {query} within {start_date}..{end_date}>"

    articles.sort(reverse=True)
    lines = [f"Google News (zh-TW) — {min(len(articles), limit)} of {len(articles)} headlines about "
             f"{query} within {start_date}..{end_date}:"]
    lines += [f"  [{p:%Y-%m-%d}] {t} (source: {s or 'unknown'})" for p, t, s in articles[:limit]]
    return "\n".join(lines)
