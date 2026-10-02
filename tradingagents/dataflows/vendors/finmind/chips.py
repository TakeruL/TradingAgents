"""Taiwan "chip" (籌碼) data from FinMind: who is buying, on what credit, and who holds.

Every series is dated by trading day and served up to the run's date. Share
counts are reported in lots (張, 1,000 shares), the unit Taiwan traders read.
"""

from __future__ import annotations

import logging
import re

from tradingagents.dataflows.errors import NoMarketDataError, VendorError
from tradingagents.dataflows.tw_common import (
    as_of_or_today,
    days_before,
    fmt,
    markdown_table,
    require_taiwan,
    ttl_for,
)
from tradingagents.dataflows.tw_render import render_flows, render_margin
from tradingagents.dataflows.vendors.finmind.common import fetch_dataset

logger = logging.getLogger(__name__)

# FinMind's investor names, grouped the way Taiwan reports read them.
_FOREIGN = ("Foreign_Investor", "Foreign_Dealer_Self")
_TRUST = ("Investment_Trust",)
_DEALER = ("Dealer_self", "Dealer_Hedging")


def _rows(dataset: str, as_of: str, look_back_days: int, data_id: str | None = None) -> list[dict]:
    rows = fetch_dataset(
        dataset, data_id=data_id, start_date=days_before(as_of, look_back_days), end_date=as_of,
        ttl_seconds=ttl_for(as_of),
    )
    return [r for r in rows if str(r.get("date", ""))[:10] <= as_of]


def get_institutional_flows(symbol: str, as_of_date: str | None = None, look_back_days: int = 30) -> str:
    stock_id, _ = require_taiwan(symbol)
    as_of = as_of_or_today(as_of_date)
    rows = _rows("TaiwanStockInstitutionalInvestorsBuySell", as_of, look_back_days, stock_id)
    by_date: dict[str, dict[str, float]] = {}
    for r in rows:
        net = (r.get("buy") or 0) - (r.get("sell") or 0)
        by_date.setdefault(str(r["date"])[:10], {})[r.get("name")] = net / 1000
    if not by_date:
        raise NoMarketDataError(symbol, stock_id, f"no institutional trading between "
                                f"{days_before(as_of, look_back_days)} and {as_of}")
    days = [
        (d, sum(v.get(n, 0) for n in _FOREIGN), sum(v.get(n, 0) for n in _TRUST), sum(v.get(n, 0) for n in _DEALER))
        for d, v in sorted(by_date.items(), reverse=True)
    ]
    return render_flows(symbol, as_of, "FinMind", days)


def get_margin_short(symbol: str, as_of_date: str | None = None, look_back_days: int = 30) -> str:
    stock_id, _ = require_taiwan(symbol)
    as_of = as_of_or_today(as_of_date)
    rows = _rows("TaiwanStockMarginPurchaseShortSale", as_of, look_back_days, stock_id)
    if not rows:
        raise NoMarketDataError(symbol, stock_id, f"no margin data up to {as_of}")
    days = [
        {
            "date": str(r["date"])[:10],
            "margin": r.get("MarginPurchaseTodayBalance"),
            "margin_limit": r.get("MarginPurchaseLimit"),
            "short": r.get("ShortSaleTodayBalance"),
        }
        for r in sorted(rows, key=lambda r: r["date"], reverse=True)
    ]
    return render_margin(symbol, as_of, "FinMind", days)


def get_foreign_holding(symbol: str, as_of_date: str | None = None, look_back_days: int = 30) -> str:
    stock_id, _ = require_taiwan(symbol)
    as_of = as_of_or_today(as_of_date)
    rows = sorted(_rows("TaiwanStockShareholding", as_of, look_back_days, stock_id),
                  key=lambda r: r["date"], reverse=True)
    if not rows:
        raise NoMarketDataError(symbol, stock_id, f"no foreign holding data up to {as_of}")
    table = [
        [
            str(r["date"])[:10],
            fmt(r.get("ForeignInvestmentSharesRatio"), 2),
            fmt((r.get("ForeignInvestmentShares") or 0) / 1000),
            fmt(r.get("ForeignInvestmentRemainRatio"), 2),
        ]
        for r in rows
    ]
    first, last = rows[-1], rows[0]
    delta = None
    if isinstance(first.get("ForeignInvestmentSharesRatio"), (int, float)) and \
            isinstance(last.get("ForeignInvestmentSharesRatio"), (int, float)):
        delta = last["ForeignInvestmentSharesRatio"] - first["ForeignInvestmentSharesRatio"]
    return (
        f"# Foreign Ownership for {symbol.upper()} (外資持股)\n"
        f"# As of {as_of}. Source: FinMind.\n\n"
        f"Foreign holding moved {fmt(delta, 2, signed=True)} percentage points "
        f"from {str(first['date'])[:10]} to {str(last['date'])[:10]}.\n\n"
        + markdown_table(["Date", "Foreign holding %", "Foreign shares (lots)", "Remaining room %"], table)
        + "\n"
    )


_LEVEL_LOWER = re.compile(r"^\s*([\d,]+)")


def _level_floor(level: str) -> int | None:
    match = _LEVEL_LOWER.match(str(level))
    return int(match.group(1).replace(",", "")) if match else None


def get_shareholding_distribution(symbol: str, as_of_date: str | None = None, weeks: int = 8) -> str:
    """Weekly TDCC shareholding distribution: how much large holders own."""
    stock_id, _ = require_taiwan(symbol)
    as_of = as_of_or_today(as_of_date)
    rows = _rows("TaiwanStockHoldingSharesPer", as_of, weeks * 7 + 7, stock_id)
    by_date: dict[str, list[dict]] = {}
    for r in rows:
        by_date.setdefault(str(r["date"])[:10], []).append(r)
    if not by_date:
        raise NoMarketDataError(symbol, stock_id, f"no shareholding distribution up to {as_of}")

    table = []
    for day in sorted(by_date, reverse=True)[:weeks]:
        over_400 = over_1000 = 0.0
        holders = big_holders = 0
        for r in by_date[day]:
            floor = _level_floor(r.get("HoldingSharesLevel", ""))
            if floor is None:
                continue
            percent, people = r.get("percent") or 0, r.get("people") or 0
            holders += people
            if floor >= 400_001:
                over_400 += percent
                big_holders += people
            if floor >= 1_000_001:
                over_1000 += percent
        table.append([day, fmt(over_400, 2), fmt(over_1000, 2), fmt(big_holders), fmt(holders)])
    return (
        f"# Shareholding Distribution for {symbol.upper()} (集保股權分散)\n"
        f"# As of {as_of}, weekly. Source: FinMind (TDCC). Large holders own more than 400 / 1,000 lots.\n\n"
        + markdown_table(
            ["Week", "Held by >400-lot holders %", "Held by >1,000-lot holders %",
             ">400-lot holders", "All holders"], table)
        + "\n"
    )


# --- market-wide -----------------------------------------------------------

def _market_flows(as_of: str, days: int) -> str:
    rows = _rows("TaiwanStockTotalInstitutionalInvestors", as_of, days)
    by_date: dict[str, dict[str, float]] = {}
    for r in rows:
        by_date.setdefault(str(r["date"])[:10], {})[r.get("name")] = ((r.get("buy") or 0) - (r.get("sell") or 0)) / 1e8
    if not by_date:
        return ""
    table = [
        [d, fmt(sum(v.get(n, 0) for n in _FOREIGN), 1, True), fmt(sum(v.get(n, 0) for n in _TRUST), 1, True),
         fmt(sum(v.get(n, 0) for n in _DEALER), 1, True)]
        for d, v in sorted(by_date.items(), reverse=True)
    ]
    return "## Market-wide institutional net buying (TWD 100 million, 億元)\n\n" + markdown_table(
        ["Date", "Foreign", "Investment trust", "Dealers"], table)


def _market_margin(as_of: str, days: int) -> str:
    rows = _rows("TaiwanStockTotalMarginPurchaseShortSale", as_of, days)
    by_date: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_date.setdefault(str(r["date"])[:10], {})[r.get("name")] = r
    if not by_date:
        return ""
    table = []
    for d, v in sorted(by_date.items(), reverse=True):
        money = v.get("MarginPurchaseMoney", {}).get("TodayBalance")
        table.append([
            d,
            fmt(money / 1e8 if isinstance(money, (int, float)) else None, 1),
            fmt(v.get("MarginPurchase", {}).get("TodayBalance")),
            fmt(v.get("ShortSale", {}).get("TodayBalance")),
        ])
    return "## Market-wide margin balances\n\n" + markdown_table(
        ["Date", "Margin balance (TWD 100 mn)", "Margin balance (lots)", "Short balance (lots)"], table)


def _futures_positioning(as_of: str, days: int) -> str:
    rows = _rows("TaiwanFuturesInstitutionalInvestors", as_of, days, "TX")
    table = []
    for r in sorted(rows, key=lambda r: r["date"], reverse=True):
        who = str(r.get("institutional_investors") or r.get("name") or "")
        if "外資" not in who and "Foreign" not in who:
            continue
        long_oi = r.get("long_open_interest_balance_volume")
        short_oi = r.get("short_open_interest_balance_volume")
        if isinstance(long_oi, (int, float)) and isinstance(short_oi, (int, float)):
            table.append([str(r["date"])[:10], fmt(long_oi - short_oi, signed=True)])
    if not table:
        return ""
    return "## Foreign net open interest in TAIEX futures (TX, contracts)\n\n" + markdown_table(
        ["Date", "Net long (+) / short (-)"], table)


def _exchange_rate(as_of: str, days: int) -> str:
    rows = _rows("TaiwanExchangeRate", as_of, days, "USD")
    table = [
        [str(r["date"])[:10], fmt(r.get("spot_buy"), 3), fmt(r.get("spot_sell"), 3)]
        for r in sorted(rows, key=lambda r: r["date"], reverse=True)
        if isinstance(r.get("spot_buy"), (int, float)) and r["spot_buy"] > 0
    ]
    if not table:
        return ""
    return "## USD/TWD spot rate (Bank of Taiwan)\n\n" + markdown_table(["Date", "Spot buy", "Spot sell"], table)


def _taiex(as_of: str, days: int) -> str:
    rows = sorted(_rows("TaiwanStockPrice", as_of, days, "TAIEX"), key=lambda r: r["date"], reverse=True)
    if not rows:
        return ""
    table = [[str(r["date"])[:10], fmt(r.get("close"), 2), fmt(r.get("spread"), 2, True),
              fmt((r.get("Trading_money") or 0) / 1e8, 0)] for r in rows]
    return "## TAIEX (加權指數)\n\n" + markdown_table(["Date", "Close", "Change", "Turnover (TWD 100 mn)"], table)


def get_tw_market_overview(as_of_date: str | None = None, look_back_days: int = 14) -> str:
    """Market-wide flows, credit, futures positioning and the currency."""
    as_of = as_of_or_today(as_of_date)
    sections, failures = [], []
    for build in (_taiex, _market_flows, _market_margin, _futures_positioning, _exchange_rate):
        try:
            part = build(as_of, look_back_days)
        except VendorError as exc:
            logger.warning("FinMind %s unavailable: %s", build.__name__, exc)
            failures.append(exc)
            continue
        if part:
            sections.append(part)
    if not sections:
        if failures:
            raise failures[0]
        raise NoMarketDataError("TAIEX", "TAIEX", f"no market data up to {as_of}")
    return (
        f"# Taiwan Market Overview as of {as_of}\n# Source: FinMind\n\n" + "\n\n".join(sections) + "\n"
    )
