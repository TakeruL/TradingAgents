"""Taiwan stock news from FinMind (TaiwanStockNews), in Chinese, by stock code."""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.date_window import in_window
from tradingagents.dataflows.tw_common import require_taiwan, ttl_for
from tradingagents.dataflows.vendors.finmind.common import fetch_dataset

# FinMind stamps news in Taiwan time.
_TAIPEI = timezone(timedelta(hours=8))


def _published(row: dict) -> datetime | None:
    text = str(row.get("date") or "")
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=_TAIPEI)
        except ValueError:
            continue
    return None


# FinMind serves this dataset one day per request; a long window is cut to its
# latest days so one call cannot spend a large share of the hourly quota.
MAX_NEWS_DAYS = 10
MIN_PER_DAY = 3

# Titles end with their publisher, sometimes twice (" - 股市爆料同學會 - CMoney").
_PUBLISHER_SUFFIX = re.compile(r"\s+-\s+[^-]{1,24}$")


def _headline(row: dict) -> str:
    title = " ".join(str(row.get("title") or "").split())
    for _ in range(2):
        title = _PUBLISHER_SUFFIX.sub("", title)
    return title


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """News about one stock within the window, spread over its days, newest first.

    Items from CMoney are posts on its 股市爆料同學會 forum rather than press.
    """
    stock_id, _ = require_taiwan(ticker)
    limit = get_config()["news_article_limit"]
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    days = min((end_dt - start_dt).days + 1, MAX_NEWS_DAYS)
    # A busy day must not crowd out the rest of the window.
    per_day = max(MIN_PER_DAY, math.ceil(limit / max(days, 1)))
    seen, articles = set(), []
    for back in range(days):
        day = (end_dt - timedelta(days=back)).strftime("%Y-%m-%d")
        rows = fetch_dataset("TaiwanStockNews", data_id=stock_id, start_date=day, ttl_seconds=ttl_for(day))
        taken = 0
        for row in sorted(rows, key=lambda r: str(r.get("date")), reverse=True):
            title = _headline(row)
            if not title or title in seen or not in_window(_published(row), start_dt, end_dt):
                continue
            seen.add(title)
            articles.append((row, title))
            taken += 1
            if taken >= per_day:
                break
        if len(articles) >= limit:
            break
    articles = articles[:limit]
    if not articles:
        return f"No news found for {ticker} between {start_date} and {end_date}"

    lines = [
        f"### {title} (source: {row.get('source') or 'Unknown'}, {str(row.get('date'))[:16]})"
        for row, title in articles
    ]
    return (
        f"## {ticker} News, from {start_date} to {end_date} (FinMind, Chinese-language; "
        "items from CMoney are posts on its 股市爆料同學會 forum):\n\n" + "\n".join(lines) + "\n"
    )
