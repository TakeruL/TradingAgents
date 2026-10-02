"""Daily quotes for Taiwan securities from FinMind (TaiwanStockPrice)."""

from __future__ import annotations

from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.tw_common import require_taiwan, ttl_for
from tradingagents.dataflows.vendors.finmind.common import fetch_dataset


def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """OHLCV between two dates, as CSV. Prices are as traded (not dividend-adjusted)."""
    stock_id, _ = require_taiwan(symbol)
    rows = fetch_dataset(
        "TaiwanStockPrice", data_id=stock_id, start_date=start_date, end_date=end_date,
        ttl_seconds=ttl_for(end_date),
    )
    rows = [r for r in rows if start_date <= str(r.get("date", "")) <= end_date]
    if not rows:
        raise NoMarketDataError(symbol, stock_id, f"no FinMind quotes between {start_date} and {end_date}")

    lines = ["Date,Open,High,Low,Close,Volume,Change,Turnover"]
    for r in sorted(rows, key=lambda r: r["date"]):
        lines.append(
            f"{r['date']},{r.get('open')},{r.get('max')},{r.get('min')},{r.get('close')},"
            f"{r.get('Trading_Volume')},{r.get('spread')},{r.get('Trading_money')}"
        )
    header = (
        f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
        f"# Total records: {len(rows)}\n"
        "# Source: FinMind (exchange daily quotes, unadjusted). Volume in shares "
        "(1 lot = 1,000 shares); Turnover in TWD.\n\n"
    )
    return header + "\n".join(lines) + "\n"
