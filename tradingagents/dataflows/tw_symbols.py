"""Taiwan stock codes and names, resolved to the Yahoo symbol the pipeline uses.

People name a Taiwan stock by its bare code (``2330``) or its Chinese name
(``台積電``); the data path needs the exchange suffix, which the code alone does
not tell: ``2330`` is TWSE-listed (``2330.TW``) but ``6488`` trades on TPEx
(``6488.TWO``). So the suffix is looked up, once, at the entry point:

  1. FinMind's listing of every Taiwan security, ETFs included;
  2. if FinMind is unavailable, the TWSE and TPEx company registers;
  3. if neither answers, a bare code is assumed TWSE-listed (``.TW``), the
     larger market, with a warning; a name cannot be guessed and is refused.

Only runs whose ``market`` setting is ``"tw"`` resolve bare codes and names; an
already-suffixed symbol and every other ticker pass through untouched.
"""

from __future__ import annotations

import logging
import re

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.errors import VendorError

logger = logging.getLogger(__name__)

_BARE_CODE = re.compile(r"^\d{4,6}[A-Z]?$")
_SUFFIXED = re.compile(r"^\d{4,6}[A-Z]?\.(TW|TWO)$")
_SUFFIX = {"twse": ".TW", "tpex": ".TWO"}

# Corporate-form words a typed name usually leaves out.
_NAME_NOISE = ("股份有限公司", "有限公司", "公司")


class UnknownTaiwanStockError(ValueError):
    """A name that matches no Taiwan-listed security (or matches several)."""


def _listing() -> tuple[list[dict], list[str]]:
    """Every Taiwan security as ``{stock_id, name, full_name?, listing}``, and the
    exchanges whose listing could not be read (both when no source answers)."""
    from tradingagents.dataflows.vendors.finmind.listing import stock_listing
    from tradingagents.dataflows.vendors.twse.listing import company_listing

    try:
        rows = stock_listing()
        if rows:
            return rows, []
    except VendorError as exc:
        logger.warning("Taiwan stock listing from FinMind unavailable: %s", exc)
    try:
        rows, missing = company_listing()
        return rows, missing
    except VendorError as exc:
        logger.warning("Taiwan company registers from TWSE/TPEx unavailable: %s", exc)
    return [], ["twse", "tpex"]


def _clean_name(name: str) -> str:
    cleaned = re.sub(r"[\s　]+", "", name or "")
    for noise in _NAME_NOISE:
        cleaned = cleaned.replace(noise, "")
    return cleaned.upper()


def _symbol(row: dict) -> str:
    return row["stock_id"].upper() + _SUFFIX[row["listing"]]


def _resolve_code(code: str) -> str:
    rows, _ = _listing()
    for row in rows:
        if row["stock_id"].upper() == code:
            return _symbol(row)
    logger.warning(
        "Could not confirm the exchange of Taiwan code %s; assuming TWSE-listed (%s.TW). "
        "Enter %s.TWO if it trades on TPEx.", code, code, code,
    )
    return f"{code}.TW"


_EXCHANGE_NAMES = {"twse": "TWSE", "tpex": "TPEx"}


def _resolve_name(name: str) -> str:
    rows, missing = _listing()
    if not rows:
        raise UnknownTaiwanStockError(
            f"cannot look up {name!r}: no Taiwan stock listing is reachable right now; "
            "enter the stock code instead (e.g. 2330)"
        )
    wanted = _clean_name(name)
    for field in ("name", "full_name"):
        exact = [row for row in rows if wanted and _clean_name(row.get(field, "")) == wanted]
        if len(exact) == 1:
            return _symbol(exact[0])
    partial = [row for row in rows if wanted and wanted in _clean_name(row.get("name", ""))]
    if len(partial) == 1:
        return _symbol(partial[0])
    if partial:
        options = ", ".join(f"{row['stock_id']} {row['name']}" for row in partial[:8])
        raise UnknownTaiwanStockError(f"{name!r} matches several Taiwan stocks ({options}); enter the code")
    if missing:
        unread = " and ".join(_EXCHANGE_NAMES[m] for m in missing)
        raise UnknownTaiwanStockError(
            f"could not find {name!r}: the {unread} listing is unreachable right now; "
            "enter the stock code instead (e.g. 2330)"
        )
    raise UnknownTaiwanStockError(f"no Taiwan-listed stock is named {name!r}; enter the stock code instead")


def resolve_tw_symbol(raw: str) -> str:
    """Resolve a bare Taiwan code or a Chinese name to ``CODE.TW`` / ``CODE.TWO``.

    Anything else is returned unchanged for the usual normalization. Raises
    ``UnknownTaiwanStockError`` for a name that matches no listed security.
    """
    if not isinstance(raw, str) or not raw.strip():
        return raw
    text = raw.strip()
    upper = text.upper()
    if _SUFFIXED.match(upper):
        return upper
    if get_config().get("market", "tw") != "tw":
        return raw
    if _BARE_CODE.match(upper):
        return _resolve_code(upper)
    if not text.isascii():
        return _resolve_name(text)
    return raw
