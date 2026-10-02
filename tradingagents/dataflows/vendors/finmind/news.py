"""Taiwan stock news from FinMind (TaiwanStockNews), in Chinese, by stock code."""

from __future__ import annotations

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


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    stock_id, _ = require_taiwan(ticker)
    limit = get_config()["news_article_limit"]
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    seen, articles = set(), []
    # Newest day first, stopping once the article limit is reached.
    for back in range(min((end_dt - start_dt).days + 1, MAX_NEWS_DAYS)):
        day = (end_dt - timedelta(days=back)).strftime("%Y-%m-%d")
        rows = fetch_dataset("TaiwanStockNews", data_id=stock_id, start_date=day, ttl_seconds=ttl_for(day))
        for row in sorted(rows, key=lambda r: str(r.get("date")), reverse=True):
            title = str(row.get("title") or "").strip()
            if not title or title in seen or not in_window(_published(row), start_dt, end_dt):
                continue
            seen.add(title)
            articles.append(row)
        if len(articles) >= limit:
            break
    articles = articles[:limit]
    if not articles:
        return f"No news found for {ticker} between {start_date} and {end_date}"

    body = ""
    for row in articles:
        body += f"### {row['title'].strip()} (source: {row.get('source') or 'Unknown'}, {str(row.get('date'))[:16]})\n"
        if row.get("link"):
            body += f"Link: {row['link']}\n"
        body += "\n"
    return f"## {ticker} News, from {start_date} to {end_date} (FinMind, Chinese-language):\n\n{body}"
