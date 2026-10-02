"""Taiwan symbols: suffix helpers, and resolving bare codes and Chinese names.

The listing sources are stubbed, so these run without a network connection.
"""

from unittest import mock

import pytest

from cli.prompts import normalize_ticker_symbol, parse_ticker
from tradingagents.dataflows import tw_symbols
from tradingagents.dataflows.config import run_config
from tradingagents.dataflows.errors import VendorUnavailableError
from tradingagents.dataflows.symbols import safe_ticker_component, taiwan_listing, tw_stock_id
from tradingagents.dataflows.vendors.finmind import listing as finmind_listing
from tradingagents.dataflows.vendors.twse import listing as twse_listing

FINMIND_ROWS = [
    {"stock_id": "2330", "name": "台積電", "listing": "twse"},
    {"stock_id": "6488", "name": "環球晶", "listing": "tpex"},
    {"stock_id": "0050", "name": "元大台灣50", "listing": "twse"},
    {"stock_id": "00679B", "name": "元大美債20年", "listing": "tpex"},
    {"stock_id": "2303", "name": "聯電", "listing": "twse"},
    {"stock_id": "3037", "name": "欣興", "listing": "twse"},
    {"stock_id": "2881", "name": "富邦金", "listing": "twse"},
    {"stock_id": "2882", "name": "國泰金", "listing": "twse"},
]

OFFICIAL_ROWS = [
    {"stock_id": "2330", "name": "台積電", "full_name": "台灣積體電路製造股份有限公司", "listing": "twse"},
    {"stock_id": "6488", "name": "環球晶", "full_name": "環球晶圓股份有限公司", "listing": "tpex"},
]


def _unavailable():
    raise VendorUnavailableError("quota reached")


@pytest.fixture
def finmind_up():
    with mock.patch.object(finmind_listing, "stock_listing", return_value=FINMIND_ROWS), \
            mock.patch.object(twse_listing, "company_listing", side_effect=AssertionError("not needed")):
        yield


@pytest.fixture
def finmind_down():
    with mock.patch.object(finmind_listing, "stock_listing", side_effect=_unavailable), \
            mock.patch.object(twse_listing, "company_listing", return_value=(OFFICIAL_ROWS, [])):
        yield


@pytest.fixture
def all_down():
    with mock.patch.object(finmind_listing, "stock_listing", side_effect=_unavailable), \
            mock.patch.object(twse_listing, "company_listing", side_effect=_unavailable):
        yield


@pytest.mark.unit
@pytest.mark.parametrize("symbol,listing,code", [
    ("2330.TW", "twse", "2330"),
    ("6488.two", "tpex", "6488"),
    ("00679B.TWO", "tpex", "00679B"),
    ("AAPL", None, None),
    ("0700.HK", None, None),
    ("2330", None, None),
])
def test_suffix_helpers(symbol, listing, code):
    assert taiwan_listing(symbol) == listing
    assert tw_stock_id(symbol) == code


@pytest.mark.unit
@pytest.mark.parametrize("raw,expected", [
    ("2330", "2330.TW"),
    ("6488", "6488.TWO"),
    ("0050", "0050.TW"),
    ("00679b", "00679B.TWO"),
    ("台積電", "2330.TW"),
    (" 環球晶 ", "6488.TWO"),
    ("欣興", "3037.TW"),
])
def test_codes_and_names_resolve_from_finmind(finmind_up, raw, expected):
    assert tw_symbols.resolve_tw_symbol(raw) == expected


@pytest.mark.unit
@pytest.mark.parametrize("raw,expected", [
    ("6488", "6488.TWO"),
    ("台灣積體電路製造", "2330.TW"),   # full name, corporate form left out
    ("環球晶", "6488.TWO"),
])
def test_official_registers_serve_when_finmind_is_down(finmind_down, raw, expected):
    assert tw_symbols.resolve_tw_symbol(raw) == expected


@pytest.mark.unit
def test_unconfirmed_code_is_assumed_twse(finmind_down):
    # ETFs are not in the company registers; the larger market is assumed.
    assert tw_symbols.resolve_tw_symbol("0050") == "0050.TW"


@pytest.mark.unit
def test_code_resolves_even_with_every_listing_down(all_down):
    assert tw_symbols.resolve_tw_symbol("2330") == "2330.TW"


@pytest.mark.unit
def test_name_with_every_listing_down_is_refused(all_down):
    with pytest.raises(tw_symbols.UnknownTaiwanStockError, match="enter the stock code"):
        tw_symbols.resolve_tw_symbol("台積電")


@pytest.mark.unit
def test_name_missing_from_a_partial_listing_says_so():
    tpex_only = [row for row in OFFICIAL_ROWS if row["listing"] == "tpex"]
    with mock.patch.object(finmind_listing, "stock_listing", side_effect=_unavailable), \
            mock.patch.object(twse_listing, "company_listing", return_value=(tpex_only, ["twse"])):
        assert tw_symbols.resolve_tw_symbol("環球晶") == "6488.TWO"
        with pytest.raises(tw_symbols.UnknownTaiwanStockError, match="TWSE listing is unreachable"):
            tw_symbols.resolve_tw_symbol("台積電")


@pytest.mark.unit
def test_unknown_name_is_refused(finmind_up):
    with pytest.raises(tw_symbols.UnknownTaiwanStockError, match="no Taiwan-listed stock"):
        tw_symbols.resolve_tw_symbol("不存在公司")


@pytest.mark.unit
def test_ambiguous_name_lists_the_candidates(finmind_up):
    with pytest.raises(tw_symbols.UnknownTaiwanStockError, match="2881 富邦金.*2882 國泰金"):
        tw_symbols.resolve_tw_symbol("金")


@pytest.mark.unit
@pytest.mark.parametrize("raw", ["AAPL", "0700.HK", "BTC-USD", "^TWII", "2330.TW", "6488.TWO"])
def test_other_tickers_pass_through_without_a_lookup(raw):
    with mock.patch.object(tw_symbols, "_listing", side_effect=AssertionError("no lookup")):
        assert tw_symbols.resolve_tw_symbol(raw).upper() == raw.upper()


@pytest.mark.unit
def test_us_market_leaves_bare_codes_alone():
    with run_config({"market": "us"}), \
            mock.patch.object(tw_symbols, "_listing", side_effect=AssertionError("no lookup")):
        assert tw_symbols.resolve_tw_symbol("2330") == "2330"


@pytest.mark.unit
def test_cli_resolves_and_the_result_is_path_safe(finmind_up):
    assert normalize_ticker_symbol("台積電") == "2330.TW"
    assert parse_ticker("6488") == "6488.TWO"
    assert safe_ticker_component(normalize_ticker_symbol("00679B")) == "00679B.TWO"


@pytest.mark.unit
def test_cli_refuses_an_unknown_name(finmind_up):
    with pytest.raises(ValueError):
        parse_ticker("不存在公司")


@pytest.mark.unit
def test_finmind_listing_drops_repeats_and_emerging_shares():
    rows = [
        {"stock_id": "2330", "stock_name": "台積電", "type": "twse", "industry_category": "半導體業"},
        {"stock_id": "2330", "stock_name": "台積電", "type": "twse", "industry_category": "電子工業"},
        {"stock_id": "6488", "stock_name": "環球晶", "type": "tpex"},
        {"stock_id": "7777", "stock_name": "興櫃股", "type": "emerging"},
    ]
    with mock.patch.object(finmind_listing, "fetch_dataset", return_value=rows):
        assert finmind_listing.stock_listing() == [
            {"stock_id": "2330", "name": "台積電", "listing": "twse"},
            {"stock_id": "6488", "name": "環球晶", "listing": "tpex"},
        ]


@pytest.mark.unit
def test_official_listing_reads_both_registers_and_survives_one_outage():
    tpex_rows = [{"SecuritiesCompanyCode": "6488", "CompanyAbbreviation": "環球晶",
                  "CompanyName": "環球晶圓股份有限公司"}]

    def fetch(url, **kwargs):
        if url == twse_listing.TWSE_COMPANIES_URL:
            raise VendorUnavailableError("security page")
        return tpex_rows

    with mock.patch.object(twse_listing, "cached_fetch_json", side_effect=fetch):
        assert twse_listing.company_listing() == (
            [{"stock_id": "6488", "name": "環球晶", "full_name": "環球晶圓股份有限公司", "listing": "tpex"}],
            ["twse"],
        )

    twse_rows = [{"公司代號": "2330", "公司簡稱": "台積電", "公司名稱": "台灣積體電路製造股份有限公司"}]
    with mock.patch.object(twse_listing, "cached_fetch_json",
                           side_effect=lambda url, **kw: twse_rows if url == twse_listing.TWSE_COMPANIES_URL else []):
        companies, missing = twse_listing.company_listing()
        assert companies[0]["listing"] == "twse" and missing == []

    with mock.patch.object(twse_listing, "cached_fetch_json", side_effect=VendorUnavailableError("down")), \
            pytest.raises(VendorUnavailableError):
        twse_listing.company_listing()
