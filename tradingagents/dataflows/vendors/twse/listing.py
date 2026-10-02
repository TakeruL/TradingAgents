"""Listed (TWSE) and OTC (TPEx) companies, from each exchange's open data.

These are the company registers, so they hold operating companies only, not
ETFs or warrants. Either exchange may be unreachable on its own; what the other
returns is still served.
"""

from __future__ import annotations

import logging

from tradingagents.dataflows.errors import VendorUnavailableError
from tradingagents.dataflows.vendors.twse.common import cached_fetch_json

logger = logging.getLogger(__name__)

TWSE_COMPANIES_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_COMPANIES_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"

# A register changes with a listing or a rename, so a day-old copy is current enough.
_LISTING_TTL_SECONDS = 24 * 60 * 60

# TWSE labels its fields in Chinese and TPEx in English; take whichever is present.
_CODE_KEYS = ("公司代號", "SecuritiesCompanyCode")
_SHORT_NAME_KEYS = ("公司簡稱", "CompanyAbbreviation")
_FULL_NAME_KEYS = ("公司名稱", "CompanyName")


def _first(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _companies(url: str, listing: str) -> list[dict]:
    rows = cached_fetch_json(url, ttl_seconds=_LISTING_TTL_SECONDS)
    if not isinstance(rows, list):
        raise VendorUnavailableError(f"unexpected company register from {url}")
    companies = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = _first(row, _CODE_KEYS)
        if not code:
            continue
        companies.append({
            "stock_id": code,
            "name": _first(row, _SHORT_NAME_KEYS),
            "full_name": _first(row, _FULL_NAME_KEYS),
            "listing": listing,
        })
    return companies


def company_listing() -> tuple[list[dict], list[str]]:
    """Every listed and OTC company, and the registers that could not be read.

    Companies come as ``{stock_id, name, full_name, listing}`` with ``listing``
    ``"twse"`` or ``"tpex"``; the second value names the exchanges whose register
    was unreachable, so a caller can tell "not listed" from "not seen". Raises
    ``VendorUnavailableError`` only when neither exchange answered.
    """
    companies: list[dict] = []
    missing: list[str] = []
    failures = []
    for url, listing in ((TWSE_COMPANIES_URL, "twse"), (TPEX_COMPANIES_URL, "tpex")):
        try:
            companies.extend(_companies(url, listing))
        except VendorUnavailableError as exc:
            logger.warning("Could not read the %s company register: %s", listing, exc)
            failures.append(exc)
            missing.append(listing)
    if not companies and failures:
        raise failures[0]
    return companies, missing
