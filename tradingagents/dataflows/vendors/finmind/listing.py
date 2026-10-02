"""Every Taiwan-listed security FinMind knows, with its exchange."""

from __future__ import annotations

from tradingagents.dataflows.vendors.finmind.common import fetch_dataset

# A listing changes with an IPO, a delisting or a rename; a day-old copy is current enough.
_LISTING_TTL_SECONDS = 24 * 60 * 60

# FinMind's ``type`` for the two exchanges Yahoo quotes. Emerging-market
# (興櫃) shares have no Yahoo symbol, so they are left out.
_LISTINGS = ("twse", "tpex")


def stock_listing() -> list[dict]:
    """Stocks, ETFs and other listed securities as ``{stock_id, name, listing}``.

    FinMind repeats a security once per industry category it belongs to; the
    repeats are dropped.
    """
    rows = fetch_dataset("TaiwanStockInfo", ttl_seconds=_LISTING_TTL_SECONDS)
    seen = set()
    listing = []
    for row in rows:
        code = str(row.get("stock_id") or "").strip()
        kind = str(row.get("type") or "").strip().lower()
        if not code or kind not in _LISTINGS or code in seen:
            continue
        seen.add(code)
        listing.append({"stock_id": code, "name": str(row.get("stock_name") or "").strip(), "listing": kind})
    return listing
