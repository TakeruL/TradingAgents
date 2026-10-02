"""Prompt context shared by the agents: instrument identity, output language and portfolio."""

import functools
import logging
from collections.abc import Mapping
from typing import Any

from tradingagents.dataflows.date_window import is_historical
from tradingagents.dataflows.errors import VendorError
from tradingagents.dataflows.symbols import taiwan_listing, tw_stock_id
from tradingagents.dataflows.vendors.finmind.listing import stock_profile
from tradingagents.dataflows.vendors.yahoo.fundamentals import get_company_profile

logger = logging.getLogger(__name__)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Applied to every agent whose output reaches the saved report —
    analysts, researchers, debaters, research manager, trader, and
    portfolio manager — so a non-English run produces a fully localized
    report rather than a mix of languages.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    # The labelled lines are read by the program, so they keep their English
    # label and value: a translated rating line leaves the reader prose to
    # search, where a negated rating ("not a Sell") reads as the call (#1435).
    return (
        f" Write your entire response in {lang}, except the labelled lines the format"
        f" asks for (the \"**Rating**:\" line, \"FINAL TRANSACTION PROPOSAL:\"):"
        f" keep their label and value in English, exactly as specified."
    )


def opponent_argument_or_opening(text: str, opponent: str) -> str:
    """Opponent's latest argument, or an explicit opening marker when empty.

    The first speaker in each debate round receives an empty opponent response;
    interpolating it into a "refute the opponent" prompt makes the model
    fabricate the other side's position. Returning a clear "has not spoken yet"
    marker instead lets it open with its own case (#1176).
    """
    text = (text or "").strip()
    if text:
        return text
    return f"(The {opponent} has not spoken yet — open the debate with your own case.)"


def _clean_identity_value(value: Any) -> str | None:
    """Return a trimmed string, or None for empty / placeholder-ish values."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or cleaned.lower() in {"none", "n/a", "nan", "null"}:
        return None
    return cleaned


def resolve_instrument_identity(ticker: str) -> dict:
    """Resolve deterministic identity metadata (company name, sector, …) for a ticker.

    This exists to stop the pipeline from hallucinating a *different* company
    when a chart pattern suggests a different industry than the real one
    (#814): without a ground-truth name, the market analyst would pattern-match
    the price action to a narrative and invent an identity that then cascaded
    through every downstream agent.

    Best-effort by design: if yfinance is unavailable, rate-limited, or doesn't
    recognise the ticker, we return ``{}`` and the caller falls back to
    ticker-only context rather than failing before analysis starts. An answer
    is cached for the process; a failed lookup is asked again next time.

    Identity resolves for the same instrument the price path fetches
    (``XAUUSD`` -> ``GC=F``, #983).
    """
    try:
        return _identity(ticker)
    except Exception as exc:  # noqa: BLE001 — fail open, never block the run
        logger.debug("Could not resolve instrument identity for %s: %s", ticker, exc)
        return {}


def _taiwan_identity(ticker: str) -> dict:
    """The exchange listing's Chinese name and industry for a Taiwan listing, or {}."""
    try:
        profile = stock_profile(tw_stock_id(ticker))
    except VendorError as exc:
        logger.debug("No Taiwan listing profile for %s: %s", ticker, exc)
        return {}
    if not profile:
        return {}
    identity = {"exchange": "TWSE (listed)" if profile["listing"] == "twse" else "TPEx (OTC)"}
    if _clean_identity_value(profile.get("name")):
        identity["company_name"] = profile["name"]
    if _clean_identity_value(profile.get("industry")):
        identity["industry"] = profile["industry"]
    return identity


@functools.lru_cache(maxsize=256)
def _identity(ticker: str) -> dict:
    """The vendor's identity fields for ``ticker``; raises if the lookup fails.

    A Taiwan listing is named as its exchange lists it (台積電, 半導體業), which is
    how Taiwan news and forums refer to it; Yahoo's profile is the fallback.
    """
    if taiwan_listing(ticker):
        identity = _taiwan_identity(ticker)
        if identity.get("company_name"):
            return identity
    info = get_company_profile(ticker)
    identity: dict[str, str] = {}
    company_name = _clean_identity_value(info.get("longName")) or _clean_identity_value(
        info.get("shortName")
    )
    if company_name:
        identity["company_name"] = company_name
    for source_key, target_key in (
        ("sector", "sector"),
        ("industry", "industry"),
        ("exchange", "exchange"),
        ("quoteType", "quote_type"),
    ):
        value = _clean_identity_value(info.get(source_key))
        if value:
            identity[target_key] = value
    return identity


def build_instrument_context(
    ticker: str,
    asset_type: str = "stock",
    identity: Mapping[str, str] | None = None,
    trade_date: str | None = None,
) -> str:
    """Describe the exact instrument so agents preserve identity and ticker.

    When ``identity`` is provided (resolved deterministically via
    :func:`resolve_instrument_identity`), the company name and business
    classification are injected so agents anchor to the real company rather
    than pattern-matching the price chart to a wrong one (#814).

    That profile carries no historical vintage: it describes the company today.
    A run dated earlier gets the current name alone, as a way to tell the
    company apart from others rather than as what it was called then; a sector,
    industry or exchange it holds today is not given, since it may not have held
    on the analysis date.
    """
    is_crypto = asset_type == "crypto"
    instrument_label = "asset" if is_crypto else "instrument"
    context = (
        f"The {instrument_label} to analyze is `{ticker}`. "
        "The tools serve this instrument; refer to it by this exact ticker in every report and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `-USD`)."
    )

    identity = identity or {}
    name = identity.get("company_name") or identity.get("name")
    label = "Name" if is_crypto else "Company"
    details = []
    if is_historical(trade_date):
        if name:
            details.append(
                f"{label}: {name} (its current name, given only to identify it; "
                f"on {trade_date} it may have been named differently)"
            )
    else:
        if name:
            details.append(f"{label}: {name}")
        sector, industry = identity.get("sector"), identity.get("industry")
        if sector and industry:
            details.append(f"Business classification: {sector} / {industry}")
        elif sector:
            details.append(f"Sector: {sector}")
        elif industry:
            details.append(f"Industry: {industry}")
        if identity.get("exchange"):
            details.append(f"Exchange: {identity['exchange']}")

    if details:
        context += (
            f" Resolved identity: {'; '.join(details)}. "
            "Do not substitute a different company or ticker unless a tool "
            "result explicitly disproves this resolved identity."
        )

    if is_crypto:
        context += (
            " Treat it as a crypto asset rather than a company, and do not "
            "assume company fundamentals are available."
        )
    return context + taiwan_market_rules(ticker)


def taiwan_market_rules(ticker: str) -> str:
    """The Taiwan trading rules every agent should apply, for a Taiwan listing; else ""."""
    listing = taiwan_listing(ticker)
    if listing is None:
        return ""
    market = "TWSE-listed (上市)" if listing == "twse" else "TPEx OTC-traded (上櫃)"
    return (
        f" Taiwan market rules apply: it is {market}; prices are in TWD. Daily moves are capped "
        "at ±10% of the previous close (limit-up 漲停 / limit-down 跌停), so a stock can lock at "
        "the limit and leave orders unfilled. Settlement is T+2. The trading unit is a lot (張) "
        "of 1,000 shares; smaller sizes trade as odd lots (零股). Same-day round trips (現股當沖) "
        "are allowed. The exchange can flag a stock as an attention stock (注意股) or put it "
        "under disposition (處置股), which restricts trading (call auctions every few minutes, "
        "prepaid orders). On an ex-dividend or ex-rights date (除息/除權) the price drops by the "
        "distribution; regaining the pre-dividend price is called filling the gap (填息/填權). "
        "Companies publish revenue every month, by the 10th of the following month."
    )


# What each role should do differently for a Taiwan listing.
_TAIWAN_GUIDANCE = {
    "market": (
        "For this Taiwan listing: closes near ±10% are limit moves and mark extreme demand or "
        "supply; a stock locked at a limit can gap again the next day. Volume from "
        "get_stock_data is in shares (divide by 1,000 for lots). Yahoo quotes are adjusted for "
        "dividends and list them in the Dividends column, while FinMind and exchange quotes are "
        "as traded, so tell an ex-dividend gap from selling, and note whether the price has "
        "since filled the gap (填息). Watch for attention or disposition status when volume "
        "and price spike."
    ),
    "fundamentals": (
        "For this Taiwan listing, call get_monthly_revenue: monthly revenue (月營收) is the most "
        "timely operating signal. Report the latest month's MoM and YoY, the year-to-date YoY, "
        "the trend over the past year and any record high. From the statements, report the "
        "gross, operating and net margins (三率) and EPS by quarter (income figures are "
        "single-quarter; cash flows are year to date as filed), the PE and PB against their "
        "one-year range, and the cash dividend, payout and ex-dividend dates. Mention guidance "
        "from the latest earnings call (法說會) only if a tool returned it."
    ),
    "news": (
        "For this Taiwan listing, get_news returns Chinese-language Taiwan financial news; read "
        "it in full. Weigh the macro forces that move Taiwan stocks: Fed policy and US yields "
        "(get_macro_indicators 'fed_funds_rate', '10y_treasury'), the semiconductor and AI "
        "cycle, the TWD exchange rate and foreign capital flows, Taiwan's central bank (CBC) "
        "rate decisions, export orders, US-China trade and export controls, and cross-strait "
        "geopolitics (prediction-market topics such as 'Taiwan', 'China tariffs', 'Fed rate cut')."
    ),
    "trading": (
        "For this Taiwan listing, state quantities in lots (張, 1,000 shares) or odd lots (零股) "
        "and prices in TWD, and respect the ±10% daily limit: a stop-loss may not fill when the "
        "stock locks limit-down, so size the position for that gap risk. Settlement is T+2."
    ),
}


def taiwan_guidance(role: str, ticker: str) -> str:
    """Role-specific instructions for a Taiwan listing, with a leading space; else ""."""
    if not taiwan_listing(str(ticker)):
        return ""
    return " " + _TAIWAN_GUIDANCE[role]


def get_instrument_context_from_state(state: Mapping[str, Any]) -> str:
    """Return the instrument context for the current run.

    Prefers the identity-resolved context computed once at run start and
    stored on the state (see ``TradingAgentsGraph.resolve_instrument_context``).
    Falls back to a ticker-only context — with no network lookup — when the
    state was constructed without it (bare programmatic states, tests), so a
    consumer is never forced to make a yfinance call mid-graph.
    """
    context = state.get("instrument_context")
    if isinstance(context, str) and context.strip():
        return context
    return build_instrument_context(
        str(state["company_of_interest"]),
        state.get("asset_type", "stock"),
    )


def report_or_absent(text: str, source: str) -> str:
    """An analyst's report, or a marker saying it was never produced.

    A report is empty when its analyst was not selected, refused, or returned
    nothing. Interpolating that into a labelled section presents an absence as a
    blank finding, and the reading agent fills it in from nothing, the same way
    an empty opponent argument used to invite an invented rebuttal (#1176).
    """
    text = (text or "").strip()
    if text:
        return text
    return f"(No {source} report in this run: it is not available, not an empty finding.)"


def chips_section(state: Mapping[str, Any]) -> str:
    """The chips report as a prompt line for a Taiwan listing, else nothing.

    Only Taiwan listings have chip data, so other runs' prompts stay as they were
    rather than carrying a line about a report that cannot exist.
    """
    if not taiwan_listing(str(state.get("company_of_interest", ""))):
        return ""
    report = report_or_absent(state.get("chips_report", ""), "chips")
    return f"\nInstitutional flows and positioning (chips) report: {report}"


def get_portfolio_context_from_state(state: Mapping[str, Any]) -> str:
    """Return the caller's portfolio block, or a notice that none was given.

    A run without portfolio context must not read as a flat book: the agents
    would otherwise size as if the caller held nothing, which is a claim about
    an account we were never told about.
    """
    context = state.get("portfolio_context")
    if isinstance(context, str) and context.strip():
        return context
    return (
        "Portfolio context: not provided. You do not know the caller's current "
        "holdings or cash, so do not assume a flat book; give direction and "
        "sizing guidance in terms the caller can apply to their own position."
    )
