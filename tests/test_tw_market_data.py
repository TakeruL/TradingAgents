"""Taiwan market data: point-in-time rules, FinMind and TWSE/TPEx parsing, and
the FinMind -> official fallback through the router.

Fixtures are trimmed copies of real responses; no test reaches the network.
"""

import copy
import math
from unittest import mock

import pytest
import requests

import tradingagents.default_config as default_config
from tradingagents.agents import tools
from tradingagents.dataflows import router, tw_common
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.vendors.finmind import (
    chips as fm_chips,
    common as fm_common,
    fundamentals as fm_fund,
)
from tradingagents.dataflows.vendors.twse import (
    chips as tw_chips,
    common as tw_http,
    exchange,
    market as tw_market,
    revenue as tw_revenue,
)


@pytest.fixture(autouse=True)
def _fresh_vendor_state(monkeypatch):
    fm_common.reset_cooldown()
    monkeypatch.setattr(tw_http, "_next_slot", {})
    monkeypatch.setattr(tw_http, "_blocked_until", {})
    monkeypatch.setattr(tw_http.time, "sleep", lambda s: None)
    set_config(copy.deepcopy(default_config.DEFAULT_CONFIG))
    yield
    fm_common.reset_cooldown()


# --- shared rules ------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("period,stock_id,due", [
    ("2026-03-31", "2330", "2026-05-15"),
    ("2026-06-30", "2330", "2026-08-14"),
    ("2026-06-30", "2881", "2026-08-31"),   # financial holding: half-year report by Aug 31
    ("2026-09-30", "2330", "2026-11-14"),
    ("2025-12-31", "2330", "2026-03-31"),
])
def test_statement_public_date(period, stock_id, due):
    assert tw_common.statement_public_date(period, stock_id) == due


@pytest.mark.unit
def test_revenue_due_dates_and_parsing():
    assert tw_common.revenue_public_date(2026, 8) == "2026-09-10"
    assert tw_common.revenue_public_date(2025, 12) == "2026-01-10"
    assert tw_common.parse_roc_date("115/09/01") == "2026-09-01"
    assert tw_common.parse_roc_date("1150917") == "2026-09-17"
    assert tw_common.parse_roc_date("not a date") is None
    assert tw_common.parse_number("31,855,287") == 31855287
    assert tw_common.parse_number("-112,200") == -112200
    assert tw_common.parse_number("+35.00") == 35
    for blank in ("--", "", "X", " "):
        assert tw_common.parse_number(blank) is None
    assert tw_common.plain(7988000.0) == "7988000"
    assert tw_common.plain(27.25) == "27.25"
    assert tw_common.streak([3, 1, -2]) == "2 day(s) of net buying"
    assert tw_common.streak([-1, -5, 2]) == "2 day(s) of net selling"


@pytest.mark.unit
def test_require_taiwan_refuses_other_symbols_before_any_request():
    with pytest.raises(NoMarketDataError):
        tw_common.require_taiwan("AAPL")
    assert tw_common.require_taiwan("6488.TWO") == ("6488", "tpex")


# --- FinMind ------------------------------------------------------------------

def _statement_rows():
    rows = []
    quarters = {"2025-09-30": (900, 9.0), "2025-12-31": (1000, 10.0), "2026-03-31": (1100, 11.0),
                "2026-06-30": (1200, 12.0), "2025-03-31": (700, 7.0), "2025-06-30": (800, 8.0)}
    for period, (revenue, eps) in quarters.items():
        rows += [
            {"date": period, "type": "Revenue", "value": revenue, "origin_name": "營業收入"},
            {"date": period, "type": "EPS", "value": eps, "origin_name": "基本每股盈餘"},
            {"date": period, "type": "Revenue_per", "value": 100.0, "origin_name": "ignored"},
        ]
    return rows


@pytest.mark.unit
def test_statements_appear_only_after_their_filing_deadline():
    with mock.patch.object(fm_fund, "fetch_dataset", return_value=_statement_rows()):
        before = fm_fund.get_income_statement("2330.TW", "quarterly", "2026-08-13")
        after = fm_fund.get_income_statement("2330.TW", "quarterly", "2026-08-14")
    assert "2026-06-30" not in before and "2026-03-31" in before
    assert "2026-06-30" in after
    assert "Revenue_per" not in after
    # Revenue leads, as an integer amount.
    assert after.splitlines()[4].startswith("營業收入 (Revenue),1200,")


@pytest.mark.unit
def test_annual_income_sums_complete_years_only():
    with mock.patch.object(fm_fund, "fetch_dataset", return_value=_statement_rows()):
        out = fm_fund.get_income_statement("2330.TW", "annual", "2026-09-30")
    # 2025: 700 + 800 + 900 + 1000; 2026 has two quarters and is left out.
    assert "2025-12-31" in out and "2026-12-31" not in out
    assert "營業收入 (Revenue),3400" in out


@pytest.mark.unit
def test_monthly_revenue_growth_and_publication_dates():
    rows = [
        {"revenue_year": 2025, "revenue_month": 7, "revenue": 400e6, "create_time": "2025-08-10"},
        {"revenue_year": 2025, "revenue_month": 8, "revenue": 300e6, "create_time": "2025-09-09"},
        {"revenue_year": 2026, "revenue_month": 7, "revenue": 500e6, "create_time": "2026-08-07"},
        # Published early, on the 5th, though due on the 10th.
        {"revenue_year": 2026, "revenue_month": 8, "revenue": 600e6, "create_time": "2026-09-05"},
    ]
    with mock.patch.object(fm_fund, "fetch_dataset", return_value=rows):
        early = fm_fund.get_monthly_revenue("2330.TW", "2026-09-05", 3)
        before = fm_fund.get_monthly_revenue("2330.TW", "2026-09-04", 3)
    assert "| 2026-08 | 600 | +20.0 | +100.0 |" in early
    assert "2026-09-05" in early
    assert "2026-08 |" not in before and "2026-07 | 500" in before


@pytest.mark.unit
def test_finmind_flows_group_investors_in_lots():
    rows = [
        {"date": "2026-09-30", "name": "Foreign_Investor", "buy": 3_000_000, "sell": 1_000_000},
        {"date": "2026-09-30", "name": "Foreign_Dealer_Self", "buy": 0, "sell": 500_000},
        {"date": "2026-09-30", "name": "Investment_Trust", "buy": 100_000, "sell": 0},
        {"date": "2026-09-30", "name": "Dealer_self", "buy": 0, "sell": 50_000},
        {"date": "2026-09-30", "name": "Dealer_Hedging", "buy": 20_000, "sell": 0},
        {"date": "2026-09-29", "name": "Foreign_Investor", "buy": 2_000_000, "sell": 0},
    ]
    with mock.patch.object(fm_chips, "fetch_dataset", return_value=rows):
        out = fm_chips.get_institutional_flows("2330.TW", "2026-09-30", 10)
    assert "| 2026-09-30 | +1,500 | +100 | -30 | +1,570 |" in out
    assert "Foreign investors: 2 day(s) of net buying" in out


@pytest.mark.unit
def test_finmind_is_not_asked_about_other_symbols():
    with mock.patch.object(fm_common.requests, "get", side_effect=AssertionError("no request")):
        for call in (lambda: fm_fund.get_balance_sheet("AAPL"), lambda: fm_chips.get_margin_short("AAPL")):
            with pytest.raises(NoMarketDataError):
                call()


# --- TWSE / TPEx --------------------------------------------------------------

T86 = {
    "stat": "OK",
    "fields": ["證券代號", "證券名稱", "外陸資買進股數(不含外資自營商)", "外陸資賣出股數(不含外資自營商)",
               "外陸資買賣超股數(不含外資自營商)", "外資自營商買進股數", "外資自營商賣出股數", "外資自營商買賣超股數",
               "投信買進股數", "投信賣出股數", "投信買賣超股數", "自營商買賣超股數", "自營商買進股數(自行買賣)",
               "自營商賣出股數(自行買賣)", "自營商買賣超股數(自行買賣)", "自營商買進股數(避險)", "自營商賣出股數(避險)",
               "自營商買賣超股數(避險)", "三大法人買賣超股數"],
    "data": [["2330", "台積電          ", "25,569,109", "24,866,515", "702,594", "0", "0", "0", "805,000",
              "43,278", "761,722", "399,899", "312,000", "68,223", "243,777", "287,616", "131,494", "156,122",
              "1,864,215"]],
}
TPEX_INSTI = {"stat": "ok", "tables": [{
    "fields": ["代號", "名稱"] + ["買進股數", "賣出股數", "買賣超股數"] * 7 + ["三大法人買賣超股數合計"],
    "data": [["6488", "環球晶", "7,871,032", "4,095,481", "3,775,551", "0", "0", "0", "7,871,032", "4,095,481",
              "3,775,551", "0", "112,200", "-112,200", "64,158", "120,200", "-56,042", "517,007", "371,413",
              "145,594", "581,165", "491,613", "89,552", "3,752,903"]],
}]}
MI_MARGN = {"stat": "OK", "tables": [
    {"title": "信用交易統計", "fields": ["項目", "買進", "賣出", "現金(券)償還", "前日餘額", "今日餘額"],
     "data": [["融資(交易單位)", "390,286", "397,546", "9,022", "9,302,600", "9,286,318"],
              ["融券(交易單位)", "10,353", "28,511", "861", "217,999", "235,296"],
              ["融資金額(仟元)", "32,417,437", "28,214,741", "603,587", "618,653,344", "622,252,453"]]},
    {"title": "融資融券彙總", "fields": ["代號", "名稱", "買進", "賣出", "現金償還", "前日餘額", "今日餘額",
                                     "次一營業日限額", "買進", "賣出", "現券償還", "前日餘額", "今日餘額",
                                     "次一營業日限額", "資券互抵", "註記"],
     "data": [["2330", "台積電", "1,073", "498", "13", "30,134", "30,696", "6,483,092", "1", "4", "0", "15",
               "18", "6,483,092", "1", " "]]},
]}
BFI82U = {"stat": "OK", "fields": ["單位名稱", "買進金額", "賣出金額", "買賣差額"], "data": [
    ["自營商(自行買賣)", "7,572,941,960", "6,191,730,730", "1,381,211,230"],
    ["自營商(避險)", "25,863,864,479", "26,004,723,087", "-140,858,608"],
    ["投信", "23,413,007,171", "15,122,220,612", "8,290,786,559"],
    ["外資及陸資(不含外資自營商)", "395,761,657,462", "364,905,101,796", "30,856,555,666"],
    ["外資自營商", "0", "0", "0"],
    ["合計", "452,611,471,072", "412,223,776,225", "40,387,694,847"],
]}
NO_TRADING = {"stat": "很抱歉，沒有符合條件的資料!"}


def _exchange(responses: dict):
    """A cached_fetch_json stand-in answering by path and date; unknown dates are holidays."""
    def fetch(url, params=None, **kwargs):
        for (fragment, day), payload in responses.items():
            if fragment in url and day in str((params or {}).values()):
                return payload
        return NO_TRADING
    return fetch


@pytest.mark.unit
def test_twse_flows_skip_holidays_and_weekends():
    calls = []
    fetch = _exchange({("T86", "20260930"): T86, ("T86", "20260929"): T86})

    def counting(url, params=None, **kw):
        calls.append(params["date"])
        return fetch(url, params, **kw)

    with mock.patch.object(exchange, "cached_fetch_json", side_effect=counting):
        out = tw_chips.get_institutional_flows("2330.TW", "2026-09-30", 7)
    assert "| 2026-09-30 | +703 | +762 | +400 | +1,864 |" in out
    assert "TWSE official" in out
    # 9/26 and 9/27 are a weekend: never asked.
    assert "20260926" not in calls and "20260927" not in calls


@pytest.mark.unit
def test_tpex_flows_and_margin_columns():
    margin = {"stat": "ok", "tables": [{
        "fields": ["代號", "名稱", "前資餘額(張)", "資買", "資賣", "現償", "資餘額", "資屬證金", "資使用率(%)",
                   "資限額", "前券餘額(張)", "券賣", "券買", "券償", "券餘額", "券屬證金", "券使用率(%)", "券限額",
                   "資券相抵(張)", "備註"],
        "data": [["6488", "環球晶", "16,064", "1,520", "2,117", "5", "15,462", "237", "12.93", "119,528", "382",
                  "302", "9", "0", "675", "0", "0.56", "119,528", "18", ""]]}]}
    fetch = _exchange({("dailyTrade", "2026/09/30"): TPEX_INSTI, ("margin/balance", "2026/09/30"): margin})
    with mock.patch.object(exchange, "cached_fetch_json", side_effect=fetch):
        flows = tw_chips.get_institutional_flows("6488.TWO", "2026-09-30", 3)
        credit = tw_chips.get_margin_short("6488.TWO", "2026-09-30", 3)
    assert "| 2026-09-30 | +3,776 | -112 | +90 | +3,753 |" in flows
    assert "| 2026-09-30 | 15,462 | - | 675 | - | 4.37 | 12.94 |" in credit


@pytest.mark.unit
def test_twse_market_overview():
    fetch = _exchange({("BFI82U", "20260930"): BFI82U, ("MI_MARGN", "20260930"): MI_MARGN})
    with mock.patch.object(exchange, "cached_fetch_json", side_effect=fetch):
        out = tw_chips.get_tw_market_overview("2026-09-30", 3)
    assert "| 2026-09-30 | +308.6 | +82.9 | +12.4 |" in out
    assert "| 2026-09-30 | 6,222.5 | 9,286,318 | 235,296 |" in out


@pytest.mark.unit
def test_tpex_quotes_convert_lots_and_thousands():
    month = {"stat": "ok", "tables": [{"fields": ["日 期", "成交張數", "成交仟元", "開盤", "最高", "最低", "收盤",
                                                  "漲跌", "筆數"],
                                       "data": [["115/09/01", "12,770", "12,430,205", "908.00", "998.00", "908.00",
                                                 "994.00", "82.00", "31,831"]]}]}
    with mock.patch.object(exchange, "cached_fetch_json", side_effect=_exchange({("tradingStock", "2026/09/01"): month})):
        out = tw_market.get_stock_data("6488.TWO", "2026-09-01", "2026-09-01")
    assert "2026-09-01,908,998,908,994,12770000,82,12430205000" in out


@pytest.mark.unit
def test_official_revenue_is_withheld_before_it_was_due():
    rows = [{"資料年月": "11508", "公司代號": "6488", "營業收入-當月營收": "4764363",
             "營業收入-上月比較增減(%)": "-4.28", "營業收入-去年同月增減(%)": "7.60",
             "累計營業收入-當月累計營收": "38941229", "累計營業收入-前期比較增減(%)": "-3.11", "備註": "-"}]
    with mock.patch.object(tw_revenue, "cached_fetch_json", return_value=rows):
        out = tw_revenue.get_monthly_revenue("6488.TWO", "2026-09-10")
        assert "| 2026-08 | 4,764 | -4.3 | +7.6 | 38,941 | -3.1 | by 2026-09-10 |" in out
        with pytest.raises(NoMarketDataError, match="not public on 2026-09-09"):
            tw_revenue.get_monthly_revenue("6488.TWO", "2026-09-09")


# --- routing ------------------------------------------------------------------

@pytest.mark.unit
def test_finmind_quota_falls_through_to_the_official_reports():
    spent = mock.Mock(status_code=402)
    spent.json.return_value = {"msg": "Requests reach the upper limit.", "status": 402}
    fetch = _exchange({("T86", "20260930"): T86})
    with mock.patch.object(fm_common.requests, "get", return_value=spent) as finmind_get, \
            mock.patch.object(exchange, "cached_fetch_json", side_effect=fetch):
        first = router.route_to_vendor("get_institutional_flows", "2330.TW", "2026-09-30", 1)
        second = router.route_to_vendor("get_institutional_flows", "2330.TW", "2026-09-30", 1)
    assert "TWSE official" in first and "TWSE official" in second
    assert finmind_get.call_count == 1   # the cool-down spared the second request


@pytest.mark.unit
def test_an_official_outage_after_finmind_is_reported_not_raised():
    spent = mock.Mock(status_code=402)
    spent.json.return_value = {"msg": "upper limit", "status": 402}
    with mock.patch.object(fm_common.requests, "get", return_value=spent), \
            mock.patch.object(tw_http, "_get", side_effect=requests.ConnectionError("reset")):
        out = router.route_to_vendor("get_margin_short", "2330.TW", "2026-09-30", 1)
    assert out.startswith("DATA_UNAVAILABLE")


@pytest.mark.unit
def test_us_fundamentals_pass_the_taiwan_vendors_without_a_request():
    served = mock.Mock(return_value="yahoo fundamentals")
    with mock.patch.object(fm_common.requests, "get", side_effect=AssertionError("no FinMind request")), \
            mock.patch.object(tw_http.requests, "get", side_effect=AssertionError("no exchange request")), \
            mock.patch.dict(router.VENDOR_METHODS["get_fundamentals"], {"yfinance": served}):
        assert router.route_to_vendor("get_fundamentals", "AAPL", "2026-09-30") == "yahoo fundamentals"


@pytest.mark.unit
def test_taiwan_tools_say_not_applicable_for_other_symbols():
    state = {"company_of_interest": "AAPL", "trade_date": "2026-09-30"}
    with mock.patch.object(tools, "route_to_vendor", side_effect=AssertionError("not routed")):
        for tool in (tools.get_monthly_revenue, tools.get_institutional_flows, tools.get_margin_short,
                     tools.get_foreign_holding, tools.get_shareholding_distribution):
            out = tool.func(state["company_of_interest"], "2026-09-30", trade_date=state["trade_date"])
            assert out.startswith("NOT_APPLICABLE")


@pytest.mark.unit
def test_closed_ranges_are_cached_for_good():
    assert tw_common.ttl_for("2020-01-01") == math.inf
    assert tw_common.ttl_for("2999-01-01") == tw_common.LIVE_TTL_SECONDS


@pytest.mark.unit
def test_finmind_news_is_fetched_one_day_at_a_time_newest_first(monkeypatch):
    from tradingagents.dataflows.vendors.finmind import news as fm_news

    asked = []

    def fetch(dataset, data_id=None, start_date=None, end_date=None, ttl_seconds=None):
        asked.append((start_date, end_date))
        return [{"date": f"{start_date} 09:00:00", "title": f"headline {start_date} {i}",
                 "source": "cnyes", "link": "https://example.com"} for i in range(2)]

    set_config({"news_article_limit": 3})
    monkeypatch.setattr(fm_news, "fetch_dataset", fetch)
    out = fm_news.get_news("2330.TW", "2026-09-24", "2026-09-30")
    # One day per request (no end date), stopping once three articles are in hand.
    assert asked == [("2026-09-30", None), ("2026-09-29", None)]
    assert out.count("### headline") == 3 and "headline 2026-09-30 0" in out


@pytest.mark.unit
def test_finmind_news_spreads_over_the_window_and_drops_publisher_suffixes(monkeypatch):
    from tradingagents.dataflows.vendors.finmind import news as fm_news

    def fetch(dataset, data_id=None, start_date=None, end_date=None, ttl_seconds=None):
        # A busy latest day, then one story a day.
        count = 10 if start_date == "2026-10-02" else 1
        return [{"date": f"{start_date} 09:0{i}:00", "title": f"{start_date} 新聞{i} - 經濟日報",
                 "source": "經濟日報", "link": "https://example.com/very/long"} for i in range(count)] + [
            {"date": f"{start_date} 08:00:00", "title": f"{start_date} 新聞0 - finance.ettoday.net",
             "source": "finance.ettoday.net"}]

    set_config({"news_article_limit": 6})
    monkeypatch.setattr(fm_news, "fetch_dataset", fetch)
    out = fm_news.get_news("2330.TW", "2026-09-30", "2026-10-02")
    headlines = [line for line in out.splitlines() if line.startswith("###")]
    # Three days, at most max(3, ceil(6/3)) = 3 a day; the same story under two publishers once.
    assert [h.split(" (source")[0] for h in headlines] == [
        "### 2026-10-02 新聞9", "### 2026-10-02 新聞8", "### 2026-10-02 新聞7",
        "### 2026-10-01 新聞0", "### 2026-09-30 新聞0"]
    assert "http" not in out and "CMoney" in out.splitlines()[0]
