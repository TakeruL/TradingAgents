"""The latest month's revenue from the exchanges' open data (no history).

The open data holds one month per company: the latest published. It is served
only when that month was due by the run's date (the 10th of the following
month), so a backtest is never shown a later month; for an older date it is
withheld, and the history needs FinMind.
"""

from __future__ import annotations

from tradingagents.dataflows.errors import NoMarketDataError, VendorUnavailableError
from tradingagents.dataflows.tw_common import (
    as_of_or_today,
    fmt,
    markdown_table,
    parse_number,
    require_taiwan,
    revenue_public_date,
)
from tradingagents.dataflows.vendors.twse.common import cached_fetch_json

_URLS = {
    "twse": "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
    "tpex": "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O",
}
_TTL_SECONDS = 6 * 60 * 60


def get_monthly_revenue(ticker: str, as_of_date: str | None = None, months: int = 12) -> str:
    stock_id, listing = require_taiwan(ticker)
    as_of = as_of_or_today(as_of_date)
    rows = cached_fetch_json(_URLS[listing], ttl_seconds=_TTL_SECONDS)
    if not isinstance(rows, list):
        raise VendorUnavailableError("unexpected monthly revenue report from the exchange")
    row = next((r for r in rows if isinstance(r, dict) and str(r.get("公司代號", "")).strip() == stock_id), None)
    if row is None:
        raise NoMarketDataError(ticker, stock_id, "not in the exchange's latest monthly revenue report")

    period = str(row.get("資料年月", "")).strip()  # ROC year and month, e.g. 11508
    try:
        year, month = int(period[:-2]) + 1911, int(period[-2:])
    except ValueError as exc:
        raise VendorUnavailableError(f"unreadable revenue month {period!r}") from exc
    due = revenue_public_date(year, month)
    if due > as_of:
        raise NoMarketDataError(
            ticker, stock_id,
            f"the official backup holds only the latest month ({year}-{month:02d}, due {due}), "
            f"which was not public on {as_of}",
        )

    def thousands(key):  # reported in TWD thousands; shown in millions
        value = parse_number(row.get(key))
        return value / 1000 if value is not None else None

    table = [[
        f"{year}-{month:02d}",
        fmt(thousands("營業收入-當月營收")),
        fmt(parse_number(row.get("營業收入-上月比較增減(%)")), 1, signed=True),
        fmt(parse_number(row.get("營業收入-去年同月增減(%)")), 1, signed=True),
        fmt(thousands("累計營業收入-當月累計營收")),
        fmt(parse_number(row.get("累計營業收入-前期比較增減(%)")), 1, signed=True),
        f"by {due}",
    ]]
    note = str(row.get("備註", "")).strip()
    exchange = "TWSE" if listing == "twse" else "TPEx"
    return (
        f"# Monthly Revenue for {ticker.upper()}\n"
        f"# Point-in-time as of {as_of}. Source: {exchange} official open data, which holds the latest "
        "month only (earlier months need FinMind); revenue in TWD millions; growth in %.\n\n"
        + markdown_table(["Month", "Revenue", "MoM %", "YoY %", "YTD revenue", "YTD YoY %", "Published"], table)
        + (f"\n\nCompany note: {note}" if note and note != "-" else "")
        + "\n"
    )
