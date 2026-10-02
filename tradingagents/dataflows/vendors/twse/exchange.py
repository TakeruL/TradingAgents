"""The exchanges' dated JSON reports: one request per trading day (or month).

TWSE serves ``www.twse.com.tw/rwd/zh/...?date=YYYYMMDD&response=json`` and TPEx
``www.tpex.org.tw/www/zh-tw/...?date=YYYY/MM/DD&response=json``. A day without
trading answers with a non-OK ``stat`` (TWSE) or empty tables (TPEx), which is
read as "no data that day", not as an outage. A past day's answer never
changes, so it is cached for good; one request per day is the price of the
fallback, and the cache makes it a one-time price.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from tradingagents.dataflows.errors import VendorUnavailableError
from tradingagents.dataflows.tw_common import days_before, ttl_for
from tradingagents.dataflows.vendors.twse.common import cached_fetch_json

TWSE = "https://www.twse.com.tw/rwd/zh"
TPEX = "https://www.tpex.org.tw/www/zh-tw"

# The fallback reads at most this many trading days for a daily series, to keep
# a cold cache to a minute of requests at the exchanges' required spacing.
MAX_FALLBACK_DAYS = 10

_CODE_FIELDS = ("證券代號", "代號", "股票代號")


def twse_date(day: str) -> str:
    return day.replace("-", "")


def tpex_date(day: str) -> str:
    return day.replace("-", "/")


def tables(payload: Any) -> list[dict]:
    """The non-empty tables of a report; [] when the exchange has no data for the date."""
    if not isinstance(payload, dict):
        raise VendorUnavailableError("the exchange returned an unexpected report")
    if str(payload.get("stat", "")).strip().upper() != "OK":
        return []
    if "tables" in payload:
        return [t for t in payload["tables"] if isinstance(t, dict) and t.get("data")]
    if payload.get("data"):
        return [{"title": payload.get("title"), "fields": payload.get("fields"), "data": payload["data"]}]
    return []


def report(url: str, params: dict, day: str) -> list[dict]:
    """The tables of the report at ``url`` for ``day`` (cached by how settled the day is)."""
    return tables(cached_fetch_json(url, {**params, "response": "json"}, ttl_seconds=ttl_for(day)))


def stock_row(report_tables: list[dict], stock_id: str) -> tuple[list[str], list] | None:
    """``(fields, row)`` for ``stock_id`` in a whole-market report, else None."""
    for table in report_tables:
        fields = table.get("fields") or []
        if not fields or str(fields[0]).strip() not in _CODE_FIELDS:
            continue
        for row in table["data"]:
            if row and str(row[0]).strip() == stock_id:
                return [str(f) for f in fields], row
    return None


def recent_trading_days(
    as_of: str, look_back_days: int, fetch_day: Callable[[str], Any], max_days: int = MAX_FALLBACK_DAYS,
) -> list[tuple[str, Any]]:
    """``(day, fetch_day(day))`` for the latest trading days up to ``as_of``, newest first.

    Weekends are skipped without a request; a weekday ``fetch_day`` answers None
    for (a holiday) is skipped too.
    """
    found = []
    for back in range(look_back_days + 1):
        day = days_before(as_of, back)
        if datetime.strptime(day, "%Y-%m-%d").weekday() >= 5:
            continue
        result = fetch_day(day)
        if result is not None:
            found.append((day, result))
            if len(found) >= max_days:
                break
    return found


def month_starts(start_date: str, end_date: str) -> list[str]:
    """The first day of every month from ``start_date``'s to ``end_date``'s."""
    year, month = int(start_date[:4]), int(start_date[5:7])
    last = (int(end_date[:4]), int(end_date[5:7]))
    months = []
    while (year, month) <= last:
        months.append(f"{year}-{month:02d}-01")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def month_end(month_start: str) -> str:
    year, month = int(month_start[:4]), int(month_start[5:7])
    nxt = datetime(year + (month == 12), month % 12 + 1, 1)
    return days_before(nxt.strftime("%Y-%m-%d"), 1)
