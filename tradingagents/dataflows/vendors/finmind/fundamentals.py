"""Taiwan company fundamentals from FinMind, as they were public on the run's date.

FinMind dates a statement by the period it covers, so a statement is served
only once its statutory filing deadline has passed (``statement_public_date``),
and monthly revenue once it was published (FinMind's ``create_time``) or due.
Income statement figures are single-quarter; cash flow figures are year to
date, as Taiwan companies file them.
"""

from __future__ import annotations

import logging
import math
import statistics
from datetime import datetime, timedelta

import pandas as pd

from tradingagents.dataflows.date_window import get_current_date
from tradingagents.dataflows.errors import NoMarketDataError, VendorError
from tradingagents.dataflows.tw_common import (
    as_of_or_today,
    days_before,
    fmt,
    markdown_table,
    pct_change,
    plain,
    require_taiwan,
    revenue_public_date,
    statement_public_date,
    ttl_for,
)
from tradingagents.dataflows.vendors.finmind.common import fetch_dataset
from tradingagents.dataflows.vendors.finmind.listing import stock_profile

logger = logging.getLogger(__name__)

_STATEMENTS = {
    "income": ("TaiwanStockFinancialStatements", "Income Statement"),
    "balance": ("TaiwanStockBalanceSheet", "Balance Sheet"),
    "cashflow": ("TaiwanStockCashFlowsStatement", "Cash Flow"),
}
_QUARTER_ENDS = ("03-31", "06-30", "09-30", "12-31")

# The line items a reader looks for first; the rest follow in FinMind's order.
_LEAD_ITEMS = {
    "income": ("Revenue", "GrossProfit", "OperatingIncome", "PreTaxIncome", "IncomeAfterTaxes",
               "EquityAttributableToOwnersOfParent", "EPS"),
    "balance": ("TotalAssets", "CurrentAssets", "CashAndCashEquivalents", "Liabilities",
                "CurrentLiabilities", "Equity", "EquityAttributableToOwnersOfParent"),
    "cashflow": ("CashFlowsFromOperatingActivities", "CashProvidedByInvestingActivities",
                 "CashFlowsProvidedFromFinancingActivities", "PropertyAndPlantAndEquipment"),
}
_DEADLINE_NOTE = (
    "statutory deadline passed (Q1 May 15, Q2 Aug 14 [Aug 31 for financials], "
    "Q3 Nov 14, annual Mar 31)"
)


def _statement_ttl(as_of: str) -> float:
    # Periods near the run date may still be filed; older ones are settled.
    return math.inf if as_of <= days_before(get_current_date(), 150) else 24 * 60 * 60


def _public_periods(stock_id: str, kind: str, as_of: str, years: int) -> tuple[dict, dict]:
    """``({period_end: {type: value}}, {type: label})`` for periods public by ``as_of``."""
    dataset, _ = _STATEMENTS[kind]
    rows = fetch_dataset(
        dataset, data_id=stock_id, start_date=f"{int(as_of[:4]) - years}-01-01", end_date=as_of,
        ttl_seconds=_statement_ttl(as_of),
    )
    periods: dict[str, dict] = {}
    labels: dict[str, str] = {}
    for row in rows:
        kind_name, period = row.get("type"), str(row.get("date", ""))[:10]
        if not kind_name or kind_name.endswith("_per") or not period:
            continue
        if statement_public_date(period, stock_id) > as_of:
            continue
        periods.setdefault(period, {})[kind_name] = row.get("value")
        labels.setdefault(kind_name, row.get("origin_name") or kind_name)
    return periods, labels


def _annual(kind: str, periods: dict) -> dict:
    """Fiscal-year columns: year-end balances and year-to-date cash flows from
    the Q4 period; income summed over the year's four quarters when all four are public."""
    if kind != "income":
        return {p: v for p, v in periods.items() if p.endswith("12-31")}
    years: dict[str, dict] = {}
    for year in sorted({p[:4] for p in periods}):
        quarters = [periods.get(f"{year}-{end}") for end in _QUARTER_ENDS]
        if any(q is None for q in quarters):
            continue
        totals: dict[str, float] = {}
        for item in set().union(*quarters):
            values = [q.get(item) for q in quarters]
            if all(isinstance(v, (int, float)) for v in values):
                totals[item] = sum(values)
        years[f"{year}-12-31"] = totals
    return years


def _statement(kind: str, ticker: str, freq: str, as_of_date: str | None) -> str:
    stock_id, _ = require_taiwan(ticker)
    as_of = as_of_or_today(as_of_date)
    annual = str(freq).lower().startswith("annual")
    periods, labels = _public_periods(stock_id, kind, as_of, years=4 if annual else 3)
    if annual:
        periods = _annual(kind, periods)
    columns = sorted(periods, reverse=True)[: 4 if annual else 8]
    _, title = _STATEMENTS[kind]
    if not columns:
        raise NoMarketDataError(ticker, stock_id, f"no {title.lower()} public by {as_of}")

    present = [item for item in labels if any(item in periods[c] for c in columns)]
    lead = [item for item in _LEAD_ITEMS[kind] if item in present]
    items = lead + [item for item in present if item not in lead]
    frame = pd.DataFrame(
        {c: [plain(periods[c].get(item)) if isinstance(periods[c].get(item), (int, float)) else ""
             for item in items] for c in columns},
        index=[f"{labels[item]} ({item})" for item in items],
    )
    notes = [f"# Point-in-time as of {as_of}: periods whose {_DEADLINE_NOTE}"]
    if kind == "cashflow":
        notes.append("# Cash flow figures are year to date, as filed (the Q2 column covers January to June).")
    if annual and kind == "income":
        notes.append("# Annual columns sum the four quarters (EPS summed likewise).")
    header = (
        f"# {title} data for {ticker.upper()} ({'annual' if annual else 'quarterly'})\n"
        + "\n".join(notes)
        + "\n# Source: FinMind; amounts in TWD\n"
    )
    return header + frame.to_csv()


def get_income_statement(ticker: str, freq: str = "quarterly", as_of_date: str | None = None) -> str:
    return _statement("income", ticker, freq, as_of_date)


def get_balance_sheet(ticker: str, freq: str = "quarterly", as_of_date: str | None = None) -> str:
    return _statement("balance", ticker, freq, as_of_date)


def get_cashflow(ticker: str, freq: str = "quarterly", as_of_date: str | None = None) -> str:
    return _statement("cashflow", ticker, freq, as_of_date)


# --- overview --------------------------------------------------------------

def _valuation_lines(stock_id: str, as_of: str) -> list[str]:
    rows = fetch_dataset(
        "TaiwanStockPER", data_id=stock_id, start_date=days_before(as_of, 370), end_date=as_of,
        ttl_seconds=ttl_for(as_of),
    )
    rows = sorted((r for r in rows if str(r.get("date", "")) <= as_of), key=lambda r: r["date"])
    if not rows:
        return []
    latest = rows[-1]
    lines = [
        f"Valuation date: {latest['date']}",
        f"PE Ratio: {latest.get('PER')}",
        f"Price to Book: {latest.get('PBR')}",
        f"Dividend Yield: {latest.get('dividend_yield')}%",
    ]
    pers = [r["PER"] for r in rows if isinstance(r.get("PER"), (int, float)) and r["PER"] > 0]
    if len(pers) >= 20 and isinstance(latest.get("PER"), (int, float)):
        rank = sum(p <= latest["PER"] for p in pers) / len(pers) * 100
        lines.append(
            f"PE 1-year range: low {min(pers):.2f} / median {statistics.median(pers):.2f} / "
            f"high {max(pers):.2f}; the latest is above {rank:.0f}% of the year's readings"
        )
    return lines


def _earnings_lines(stock_id: str, as_of: str) -> list[str]:
    periods, _ = _public_periods(stock_id, "income", as_of, years=2)
    recent = sorted(periods, reverse=True)[:4]
    if not recent:
        return []
    latest = periods[recent[0]]
    lines = [f"Latest public quarter: {recent[0]}"]
    revenue = latest.get("Revenue")
    for label, item in (("Gross Margin", "GrossProfit"), ("Operating Margin", "OperatingIncome"),
                        ("Net Margin", "IncomeAfterTaxes")):
        value = latest.get(item)
        if isinstance(value, (int, float)) and revenue:
            lines.append(f"{label} (latest quarter): {value / revenue * 100:.1f}%")
    if isinstance(latest.get("EPS"), (int, float)):
        lines.append(f"EPS (latest quarter): {latest['EPS']}")
    eps = [periods[p].get("EPS") for p in recent]
    if len(eps) == 4 and all(isinstance(e, (int, float)) for e in eps):
        lines.append(f"EPS (trailing four quarters): {sum(eps):.2f}")
    revenues = [periods[p].get("Revenue") for p in recent]
    if len(revenues) == 4 and all(isinstance(r, (int, float)) for r in revenues):
        lines.append(f"Revenue (trailing four quarters, TWD): {fmt(sum(revenues))}")
    return lines


def _dividend_lines(stock_id: str, as_of: str) -> list[str]:
    rows = fetch_dataset(
        "TaiwanStockDividend", data_id=stock_id, start_date=days_before(as_of, 6 * 365), end_date=as_of,
        ttl_seconds=ttl_for(as_of),
    )
    public = [
        r for r in rows
        if str(r.get("AnnouncementDate") or r.get("date") or "")[:10] <= as_of
    ]
    if not public:
        return []
    table = []
    for r in sorted(public, key=lambda r: str(r.get("date")), reverse=True)[:6]:
        cash = sum(v for v in (r.get("CashEarningsDistribution"), r.get("CashStatutorySurplus"))
                   if isinstance(v, (int, float)))
        stock = sum(v for v in (r.get("StockEarningsDistribution"), r.get("StockStatutorySurplus"))
                    if isinstance(v, (int, float)))
        table.append([
            str(r.get("year", "")), fmt(cash, 2), fmt(stock, 2),
            r.get("CashExDividendTradingDate") or "-", r.get("CashDividendPaymentDate") or "-",
        ])
    return ["", "Dividends declared (TWD per share):", markdown_table(
        ["Earnings period", "Cash", "Stock", "Cash ex-dividend date", "Payment date"], table)]


def get_fundamentals(ticker: str, as_of_date: str | None = None) -> str:
    """Valuation, latest public earnings and dividends, as of ``as_of_date``."""
    stock_id, listing = require_taiwan(ticker)
    as_of = as_of_or_today(as_of_date)
    lines: list[str] = []
    try:
        profile = stock_profile(stock_id)
    except VendorError:
        profile = None
    if profile:
        lines.append(f"Name: {profile['name']}")
        if profile.get("industry"):
            lines.append(f"Industry (current classification): {profile['industry']}")
    lines.append(f"Market: {'TWSE (listed)' if listing == 'twse' else 'TPEx (OTC)'}")

    sections = 0
    for build in (_valuation_lines, _earnings_lines, _dividend_lines):
        try:
            part = build(stock_id, as_of)
        except NoMarketDataError:
            part = []
        except VendorError as exc:
            # A section's own outage leaves the others standing.
            if build is _valuation_lines:
                raise
            logger.warning("FinMind %s unavailable for %s: %s", build.__name__, ticker, exc)
            part = [f"({build.__name__.strip('_').replace('_lines', '')} data unavailable: {exc})"]
        if part:
            sections += 1
            lines.extend(part)
    if not sections:
        raise NoMarketDataError(ticker, stock_id, f"no FinMind fundamentals as of {as_of}")
    return (
        f"# Company Fundamentals for {ticker.upper()}\n"
        f"# Point-in-time as of: {as_of}. Source: FinMind\n\n" + "\n".join(lines)
    )


# --- monthly revenue -------------------------------------------------------

def _revenue_visible(row: dict, as_of: str) -> str | None:
    """The date the row counts as public, if that is on or before ``as_of``."""
    year, month = int(row["revenue_year"]), int(row["revenue_month"])
    due = revenue_public_date(year, month)
    published = str(row.get("create_time") or "")[:10]
    # A record FinMind created after the due date was still public by then.
    public = min(published, due) if published else due
    return public if public <= as_of else None


def get_monthly_revenue(ticker: str, as_of_date: str | None = None, months: int = 12) -> str:
    """Monthly revenue with MoM, YoY and year-to-date growth, as published by ``as_of_date``."""
    stock_id, _ = require_taiwan(ticker)
    as_of = as_of_or_today(as_of_date)
    months = max(1, min(int(months or 12), 36))
    start = (datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=(months + 14) * 31)).strftime("%Y-%m-01")
    rows = fetch_dataset(
        "TaiwanStockMonthRevenue", data_id=stock_id, start_date=start, end_date=as_of,
        ttl_seconds=ttl_for(as_of),
    )
    revenue: dict[tuple[int, int], float] = {}
    published: dict[tuple[int, int], str] = {}
    for row in rows:
        try:
            key = (int(row["revenue_year"]), int(row["revenue_month"]))
        except (KeyError, TypeError, ValueError):
            continue
        public = _revenue_visible(row, as_of)
        if public is None or not isinstance(row.get("revenue"), (int, float)):
            continue
        revenue[key], published[key] = float(row["revenue"]), public
    if not revenue:
        raise NoMarketDataError(ticker, stock_id, f"no monthly revenue published by {as_of}")

    def prev(key):
        year, month = key
        return (year - 1, 12) if month == 1 else (year, month - 1)

    def ytd(key):
        year, month = key
        values = [revenue.get((year, m)) for m in range(1, month + 1)]
        return sum(values) if all(v is not None for v in values) else None

    table = []
    for key in sorted(revenue, reverse=True)[:months]:
        year, month = key
        last_year = (year - 1, month)
        table.append([
            f"{year}-{month:02d}",
            fmt(revenue[key] / 1e6),
            fmt(pct_change(revenue[key], revenue.get(prev(key))), 1, signed=True),
            fmt(pct_change(revenue[key], revenue.get(last_year)), 1, signed=True),
            fmt(ytd(key) / 1e6 if ytd(key) is not None else None),
            fmt(pct_change(ytd(key), ytd(last_year)), 1, signed=True),
            published[key],
        ])
    latest = max(revenue)
    window = [revenue[k] for k in sorted(revenue, reverse=True)[:months]]
    notes = []
    if revenue[latest] >= max(window) and len(window) > 1:
        notes.append(f"{latest[0]}-{latest[1]:02d} revenue is the highest of the {len(window)} months shown.")
    return (
        f"# Monthly Revenue for {ticker.upper()}\n"
        f"# Point-in-time as of {as_of}: months published (or due, the 10th of the next month) by then.\n"
        "# Source: FinMind; revenue in TWD millions; growth in %.\n\n"
        + markdown_table(
            ["Month", "Revenue", "MoM %", "YoY %", "YTD revenue", "YTD YoY %", "Published"], table)
        + ("\n\n" + " ".join(notes) if notes else "")
        + "\n"
    )
