"""Official daily quotes and valuation ratios for one Taiwan security."""

from __future__ import annotations

from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.tw_common import (
    as_of_or_today,
    days_before,
    parse_number,
    parse_roc_date,
    plain,
    require_taiwan,
)
from tradingagents.dataflows.vendors.twse.exchange import (
    TPEX,
    TWSE,
    month_end,
    month_starts,
    recent_trading_days,
    report,
    stock_row,
    tpex_date,
    twse_date,
)

# A price range longer than this many months is cut to its latest months:
# each month is a request at the exchange's pace.
MAX_MONTHS = 13


def _month_rows(stock_id: str, listing: str, month: str) -> list[list]:
    """One month of a stock's daily quotes as ``[date, open, high, low, close, shares, change, value]``."""
    # Both answer 日期, volume, value, open, high, low, close, change, trades;
    # TWSE in shares and TWD, TPEx in lots and TWD thousands.
    if listing == "twse":
        found = report(f"{TWSE}/afterTrading/STOCK_DAY", {"date": twse_date(month), "stockNo": stock_id},
                       month_end(month))
        unit = 1
    else:
        found = report(f"{TPEX}/afterTrading/tradingStock", {"code": stock_id, "date": tpex_date(month)},
                       month_end(month))
        unit = 1000
    rows = []
    for table in found:
        for raw in table["data"]:
            day = parse_roc_date(raw[0])
            if not day or len(raw) < 8:
                continue
            o, h, low, c, vol, chg, value = (parse_number(raw[i]) for i in (3, 4, 5, 6, 1, 7, 2))
            rows.append([day, o, h, low, c, vol * unit if vol is not None else None, chg,
                         value * unit if value is not None else None])
    return rows


def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    stock_id, listing = require_taiwan(symbol)
    months = month_starts(start_date, end_date)
    note = ""
    if len(months) > MAX_MONTHS:
        months = months[-MAX_MONTHS:]
        note = f"# Range cut to the latest {MAX_MONTHS} months (from {months[0]}).\n"
    rows = [
        r for month in months for r in _month_rows(stock_id, listing, month)
        if start_date <= r[0] <= end_date
    ]
    if not rows:
        raise NoMarketDataError(symbol, stock_id, f"no official quotes between {start_date} and {end_date}")

    lines = ["Date,Open,High,Low,Close,Volume,Change,Turnover"]
    lines += [",".join([r[0]] + [plain(v) for v in r[1:]]) for r in sorted(rows)]
    exchange = "TWSE" if listing == "twse" else "TPEx"
    return (
        f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
        f"# Total records: {len(rows)}\n"
        f"# Source: {exchange} official daily quotes (unadjusted). Volume in shares; Turnover in TWD.\n"
        + note + "\n" + "\n".join(lines) + "\n"
    )


def _twse_valuation(stock_id: str, as_of: str) -> dict | None:
    # One request returns the month's daily ratios; early in a month the latest
    # trading day may sit in the previous one.
    for month in (as_of[:8] + "01", days_before(as_of[:8] + "01", 1)[:8] + "01"):
        found = report(f"{TWSE}/afterTrading/BWIBBU", {"date": twse_date(month), "stockNo": stock_id},
                       min(month_end(month), as_of))
        rows = [(parse_roc_date(r[0]), r) for t in found for r in t["data"] if r]
        rows = [(d, r) for d, r in rows if d and d <= as_of]
        if rows:
            day, r = max(rows, key=lambda x: x[0])
            # 日期, 殖利率(%), 股利年度, 本益比, 股價淨值比, 財報年/季
            return {"date": day, "yield": r[1], "dividend_year": r[2], "pe": r[3], "pb": r[4],
                    "report": r[5] if len(r) > 5 else ""}
    return None


def _tpex_valuation(stock_id: str, as_of: str) -> dict | None:
    def fetch(day):
        hit = stock_row(report(f"{TPEX}/afterTrading/peQryDate", {"date": tpex_date(day)}, day), stock_id)
        return hit[1] if hit else None

    found = recent_trading_days(as_of, 7, fetch, max_days=1)
    if not found:
        return None
    day, r = found[0]
    # 股票代號, 公司名稱, 本益比, 每股股利, 股利年度, 殖利率(%), 股價淨值比, 財報年/季
    return {"date": day, "pe": r[2], "dividend": r[3], "dividend_year": r[4], "yield": r[5], "pb": r[6],
            "report": r[7] if len(r) > 7 else ""}


def get_fundamentals(ticker: str, as_of_date: str | None = None) -> str:
    """Valuation ratios only: the official backup has no earnings or dividend history."""
    stock_id, listing = require_taiwan(ticker)
    as_of = as_of_or_today(as_of_date)
    value = _twse_valuation(stock_id, as_of) if listing == "twse" else _tpex_valuation(stock_id, as_of)
    if not value:
        raise NoMarketDataError(ticker, stock_id, f"no official valuation ratios up to {as_of}")
    lines = [
        f"Market: {'TWSE (listed)' if listing == 'twse' else 'TPEx (OTC)'}",
        f"Valuation date: {value['date']}",
        f"PE Ratio: {str(value['pe']).strip() or '-'}",
        f"Price to Book: {str(value['pb']).strip() or '-'}",
        f"Dividend Yield: {str(value['yield']).strip() or '-'}%",
    ]
    dividend = parse_number(value.get("dividend"))
    if dividend:
        lines.append(f"Dividend per share: {plain(dividend)} (ROC fiscal year {value.get('dividend_year')})")
    if value.get("report"):
        lines.append(f"Earnings basis (latest financial report): {value['report']}")
    exchange = "TWSE" if listing == "twse" else "TPEx"
    return (
        f"# Company Fundamentals for {ticker.upper()}\n"
        f"# Point-in-time as of: {as_of}. Source: {exchange} official (valuation ratios only; "
        "earnings, margins and dividend history are not in this backup).\n\n" + "\n".join(lines)
    )
