"""Official institutional trading and margin data, one whole-market report per day."""

from __future__ import annotations

from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.tw_common import (
    as_of_or_today,
    fmt,
    markdown_table,
    parse_number,
    require_taiwan,
)
from tradingagents.dataflows.tw_render import render_flows, render_margin
from tradingagents.dataflows.vendors.twse.exchange import (
    TPEX,
    TWSE,
    recent_trading_days,
    report,
    stock_row,
    tpex_date,
    twse_date,
)


def _source(listing: str) -> str:
    return f"{'TWSE' if listing == 'twse' else 'TPEx'} official (latest trading days only)"


def _twse_flows(fields: list[str], row: list) -> tuple[float, float, float]:
    """Net shares by group from a T86 row, located by column name.

    Foreign = 外陸資 (excluding foreign dealers) + 外資自營商; dealers = the 自營商 total.
    """
    def net(match):
        return sum(parse_number(row[i]) or 0 for i, f in enumerate(fields) if match(f))

    foreign = net(lambda f: "買賣超" in f and f.startswith("外"))
    trust = net(lambda f: "買賣超" in f and f.startswith("投信"))
    dealer = net(lambda f: f.startswith("自營商買賣超") and "(" not in f)
    return foreign, trust, dealer


def _tpex_flows(row: list) -> tuple[float, float, float]:
    # Columns come in buy/sell/net triples: foreign excl. dealers, foreign dealers,
    # foreign total, trusts, dealers' own, dealers' hedging, dealers total; then the sum.
    return tuple(parse_number(row[i]) or 0 for i in (10, 13, 22))


def get_institutional_flows(symbol: str, as_of_date: str | None = None, look_back_days: int = 30) -> str:
    stock_id, listing = require_taiwan(symbol)
    as_of = as_of_or_today(as_of_date)

    def fetch(day):
        if listing == "twse":
            found = report(f"{TWSE}/fund/T86", {"date": twse_date(day), "selectType": "ALLBUT0999"}, day)
        else:
            found = report(f"{TPEX}/insti/dailyTrade",
                           {"type": "Daily", "sect": "EW", "date": tpex_date(day)}, day)
        if not found:
            return None  # no trading that day
        hit = stock_row(found, stock_id)
        if hit is None:
            return (0.0, 0.0, 0.0)  # traded, but no institutional activity in this stock
        fields, row = hit
        return _twse_flows(fields, row) if listing == "twse" else _tpex_flows(row)

    days = recent_trading_days(as_of, look_back_days, fetch)
    if not days:
        raise NoMarketDataError(symbol, stock_id, f"no official institutional data up to {as_of}")
    lots = [(day, f / 1000, t / 1000, d / 1000) for day, (f, t, d) in days]
    return render_flows(symbol, as_of, _source(listing), lots)


def get_margin_short(symbol: str, as_of_date: str | None = None, look_back_days: int = 30) -> str:
    stock_id, listing = require_taiwan(symbol)
    as_of = as_of_or_today(as_of_date)

    def fetch(day):
        if listing == "twse":
            found = report(f"{TWSE}/marginTrading/MI_MARGN", {"date": twse_date(day), "selectType": "ALL"}, day)
            columns = (6, 7, 12)  # 融資今日餘額, 融資限額, 融券今日餘額
        else:
            found = report(f"{TPEX}/margin/balance", {"date": tpex_date(day)}, day)
            columns = (6, 9, 14)  # 資餘額, 資限額, 券餘額
        if not found:
            return None
        hit = stock_row(found, stock_id)
        if hit is None:
            return {}
        row = hit[1]
        margin, limit, short = (parse_number(row[i]) if i < len(row) else None for i in columns)
        return {"margin": margin, "margin_limit": limit, "short": short}

    days = [dict(date=day, **values) for day, values in recent_trading_days(as_of, look_back_days, fetch)]
    days = [d for d in days if d.get("margin") is not None or d.get("short") is not None]
    if not days:
        raise NoMarketDataError(symbol, stock_id, f"no official margin data up to {as_of}")
    return render_margin(symbol, as_of, _source(listing), days)


def get_tw_market_overview(as_of_date: str | None = None, look_back_days: int = 14) -> str:
    """TWSE market-wide institutional flows and margin totals."""
    as_of = as_of_or_today(as_of_date)

    def fetch(day):
        flows = report(f"{TWSE}/fund/BFI82U", {"dayDate": twse_date(day), "type": "day"}, day)
        if not flows:
            return None
        totals = {str(r[0]).strip(): parse_number(r[3]) for t in flows for r in t["data"] if len(r) > 3}
        margin = report(f"{TWSE}/marginTrading/MI_MARGN", {"date": twse_date(day), "selectType": "ALL"}, day)
        credit = {str(r[0]).strip(): parse_number(r[5]) for t in margin[:1] for r in t["data"] if len(r) > 5}
        return totals, credit

    days = recent_trading_days(as_of, look_back_days, fetch, max_days=5)
    if not days:
        raise NoMarketDataError("TAIEX", "TAIEX", f"no official market data up to {as_of}")

    def group(totals, *prefixes):
        return sum(v or 0 for k, v in totals.items() if k.startswith(prefixes) and k != "合計") / 1e8

    flows = [[day, fmt(group(t, "外資"), 1, True), fmt(group(t, "投信"), 1, True), fmt(group(t, "自營商"), 1, True)]
             for day, (t, _) in days]
    credit = [[day, fmt(c.get("融資金額(仟元)", 0) / 1e5 if c.get("融資金額(仟元)") else None, 1),
               fmt(c.get("融資(交易單位)")), fmt(c.get("融券(交易單位)"))]
              for day, (_, c) in days]
    return (
        f"# Taiwan Market Overview as of {as_of}\n"
        "# Source: TWSE official (listed market only; futures positioning and the exchange rate "
        "are not in this backup)\n\n"
        "## Market-wide institutional net buying (TWD 100 million, 億元)\n\n"
        + markdown_table(["Date", "Foreign", "Investment trust", "Dealers"], flows)
        + "\n\n## Market-wide margin balances\n\n"
        + markdown_table(["Date", "Margin balance (TWD 100 mn)", "Margin balance (lots)", "Short balance (lots)"],
                         credit)
        + "\n"
    )
