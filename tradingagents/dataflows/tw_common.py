"""Shared rules for Taiwan market data, used by the FinMind and TWSE/TPEx vendors.

- ``require_taiwan`` turns a non-Taiwan symbol into ``NoMarketDataError`` before
  any request, so a vendor chain falls through to the next vendor at no cost.
- Point-in-time dates: a quarterly statement counts as public on its statutory
  deadline, monthly revenue on the 10th of the following month, unless the
  vendor reports when it was actually published.
- Parsing for the exchanges' formats: ROC (民國) dates, numbers with thousands
  separators and placeholder dashes.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta

from tradingagents.dataflows.date_window import get_current_date
from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.symbols import taiwan_listing, tw_stock_id

# A response for a range that ended before today can no longer change.
LIVE_TTL_SECONDS = 60 * 60


def require_taiwan(symbol: str) -> tuple[str, str]:
    """``(stock_id, listing)`` for a Taiwan symbol, else ``NoMarketDataError``."""
    listing = taiwan_listing(symbol)
    if listing is None:
        raise NoMarketDataError(symbol, symbol, "not a Taiwan-listed symbol (.TW / .TWO)")
    return tw_stock_id(symbol), listing


def not_taiwan_notice(tool: str, symbol: str) -> str:
    """What a Taiwan-only tool returns for any other instrument."""
    return (
        f"NOT_APPLICABLE: {tool} covers Taiwan-listed securities (.TW / .TWO) only; "
        f"'{symbol}' is not one. This says nothing about the instrument; skip this data."
    )


def ttl_for(end_date: str | None) -> float:
    """Cache lifetime for a response covering up to ``end_date``."""
    if end_date and end_date < get_current_date():
        return math.inf
    return LIVE_TTL_SECONDS


def as_of_or_today(as_of_date: str | None) -> str:
    return as_of_date or get_current_date()


def days_before(day: str, days: int) -> str:
    return (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")


# --- point in time ---------------------------------------------------------

# Statutory filing deadlines (證券交易法 §36): Q1/Q2/Q3 within 45 days of the
# quarter's end, the annual report by March 31. Banks, insurers and financial
# holding companies file the half-year report by August 31 instead.
_QUARTER_DEADLINES = {3: (5, 15), 6: (8, 14), 9: (11, 14)}
_FINANCIAL_HALF_YEAR_DEADLINE = (8, 31)


def _is_financial(stock_id: str) -> bool:
    # TWSE groups banks, insurers and financial holdings under codes 28xx and 58xx.
    return stock_id[:2] in ("28", "58")


def statement_public_date(period_end: str, stock_id: str = "") -> str:
    """The date a statement for ``period_end`` must be public by, YYYY-MM-DD.

    The deadline, not the actual filing date, which no free vendor reports:
    a company that files early is seen late, never the other way around.
    """
    end = datetime.strptime(period_end[:10], "%Y-%m-%d").date()
    if end.month == 12:
        due = date(end.year + 1, 3, 31)
    elif end.month == 6 and _is_financial(stock_id):
        due = date(end.year, *_FINANCIAL_HALF_YEAR_DEADLINE)
    elif end.month in _QUARTER_DEADLINES:
        due = date(end.year, *_QUARTER_DEADLINES[end.month])
    else:
        due = end + timedelta(days=90)  # an off-calendar period: a generous bound
    return due.isoformat()


def revenue_public_date(year: int, month: int) -> str:
    """Monthly revenue is due by the 10th of the following month."""
    nxt = date(year + (month == 12), month % 12 + 1, 10)
    return nxt.isoformat()


# --- parsing ---------------------------------------------------------------

_ROC_DATE = re.compile(r"^(\d{2,3})/?(\d{2})/?(\d{2})$")


def parse_roc_date(text: str) -> str | None:
    """``115/09/01`` or ``1150901`` (ROC year 115 = 2026) -> ``2026-09-01``."""
    match = _ROC_DATE.match(str(text).strip())
    if not match:
        return None
    year, month, day = (int(g) for g in match.groups())
    try:
        return date(year + 1911, month, day).isoformat()
    except ValueError:
        return None


def parse_number(value) -> float | None:
    """``"31,855,287"`` -> 31855287.0; dashes, blanks and markers -> None."""
    if isinstance(value, (int, float)):
        return None if isinstance(value, float) and math.isnan(value) else float(value)
    text = str(value).strip().replace(",", "").replace("+", "")
    if not text or text in {"-", "--", "---", "X", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


# --- rendering -------------------------------------------------------------

def fmt(value, decimals: int = 0, signed: bool = False) -> str:
    """A number with thousands separators; ``-`` for a missing one."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:,.{decimals}f}"


def plain(value) -> str:
    """A number without exponent or trailing ``.0``: 7988000 not 7.988e+06; '' for None."""
    if value is None:
        return ""
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.4f}".rstrip("0")


def pct_change(new, old) -> float | None:
    if new is None or old in (None, 0):
        return None
    return (new - old) / abs(old) * 100


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def streak(values: list[float | None]) -> str:
    """The run of same-sign values at the start of a newest-first series."""
    count, sign = 0, 0
    for value in values:
        if value is None or value == 0:
            break
        current = 1 if value > 0 else -1
        if sign and current != sign:
            break
        sign, count = current, count + 1
    if not count:
        return "no streak"
    return f"{count} day(s) of net {'buying' if sign > 0 else 'selling'}"
