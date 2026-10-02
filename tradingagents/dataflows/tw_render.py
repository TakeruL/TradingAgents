"""Tables shared by every Taiwan chip-data vendor, so a fallback reads like the primary."""

from __future__ import annotations

from tradingagents.dataflows.tw_common import fmt, markdown_table, pct_change, streak


def _window_sum(values: list[float | None], days: int) -> float | None:
    window = [v for v in values[:days] if v is not None]
    return sum(window) if window else None


def flows_summary(dates: list[str], foreign: list, trust: list, dealer: list) -> str:
    """Streaks and 5/10/20-day sums for newest-first net-buy series in lots."""
    lines = []
    for label, series in (("Foreign investors", foreign), ("Investment trusts", trust), ("Dealers", dealer)):
        sums = ", ".join(
            f"{days}d {fmt(_window_sum(series, days), signed=True)}" for days in (5, 10, 20) if len(series) >= days
        ) or f"{len(series)}d {fmt(_window_sum(series, len(series)), signed=True)}"
        lines.append(f"- {label}: {streak(series)}; net lots {sums}")
    return f"Summary through {dates[0]}:\n" + "\n".join(lines)


def render_flows(symbol: str, as_of: str, source: str, days: list[tuple[str, float, float, float]]) -> str:
    """``days`` newest first as ``(date, foreign, trust, dealer)`` net lots."""
    table = [
        [d, fmt(f, signed=True), fmt(t, signed=True), fmt(dl, signed=True), fmt(f + t + dl, signed=True)]
        for d, f, t, dl in days
    ]
    return (
        f"# Institutional Net Buying for {symbol.upper()} (三大法人買賣超)\n"
        f"# As of {as_of}. Source: {source}. Net lots (1 lot = 1,000 shares); + is net buying.\n\n"
        + flows_summary([d[0] for d in days], [d[1] for d in days], [d[2] for d in days], [d[3] for d in days])
        + "\n\n"
        + markdown_table(["Date", "Foreign", "Investment trust", "Dealers", "Total"], table)
        + "\n"
    )


def render_margin(symbol: str, as_of: str, source: str, days: list[dict]) -> str:
    """``days`` newest first with margin/short balances and limits in lots."""
    table = []
    for i, day in enumerate(days):
        prior = days[i + 1] if i + 1 < len(days) else None
        margin, short = day.get("margin"), day.get("short")
        table.append([
            day["date"],
            fmt(margin),
            fmt(margin - prior["margin"], signed=True) if prior and margin is not None and prior.get("margin") is not None else "-",
            fmt(short),
            fmt(short - prior["short"], signed=True) if prior and short is not None and prior.get("short") is not None else "-",
            fmt(short / margin * 100, 2) if margin and short is not None else "-",
            fmt(margin / day["margin_limit"] * 100, 2) if margin is not None and day.get("margin_limit") else "-",
        ])
    first, last = days[-1], days[0]
    change = pct_change(last.get("margin"), first.get("margin"))
    summary = (
        f"Margin balance {fmt(first.get('margin'))} -> {fmt(last.get('margin'))} lots "
        f"({fmt(change, 1, signed=True)}%) from {first['date']} to {last['date']}; "
        f"short balance {fmt(first.get('short'))} -> {fmt(last.get('short'))} lots."
    )
    return (
        f"# Margin Trading and Short Selling for {symbol.upper()} (融資融券)\n"
        f"# As of {as_of}. Source: {source}. Balances in lots; short/margin ratio (券資比) and "
        "margin utilization (融資使用率) in %.\n\n"
        + summary + "\n\n"
        + markdown_table(
            ["Date", "Margin balance", "Change", "Short balance", "Change", "Short/Margin %", "Margin used %"],
            table)
        + "\n"
    )
