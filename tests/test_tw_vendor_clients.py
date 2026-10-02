"""FinMind and TWSE/TPEx clients: error mapping, quota cool-down, throttling, caching.

``requests.get`` is stubbed, so these run without a network connection.
"""

import math
from unittest import mock

import pytest
import requests

from tradingagents.dataflows.errors import VendorNotConfiguredError, VendorUnavailableError
from tradingagents.dataflows.vendors.finmind import common as finmind
from tradingagents.dataflows.vendors.twse import common as twse


def _response(status=200, payload=None, text=None, content_type="application/json"):
    response = mock.Mock()
    response.status_code = status
    response.headers = {"Content-Type": content_type}
    if payload is None:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = payload
    response.text = text if text is not None else str(payload)
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"{status}", response=response)
    else:
        response.raise_for_status.return_value = None
    return response


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    finmind.reset_cooldown()
    monkeypatch.setattr(twse, "_next_slot", {})
    monkeypatch.setattr(twse, "_blocked_until", {})
    monkeypatch.setattr(twse.time, "sleep", lambda seconds: None)
    yield
    finmind.reset_cooldown()


# --- FinMind ---------------------------------------------------------------

@pytest.mark.unit
def test_finmind_returns_rows_and_sends_the_token_as_a_header(monkeypatch):
    monkeypatch.setenv("FINMIND_API_TOKEN", "secret-token")
    rows = [{"stock_id": "2330", "close": 1000}]
    with mock.patch.object(finmind.requests, "get",
                           return_value=_response(payload={"status": 200, "msg": "success", "data": rows})) as get:
        assert finmind.fetch_dataset("TaiwanStockPrice", data_id="2330", start_date="2026-09-01") == rows
    _, kwargs = get.call_args
    assert kwargs["headers"] == {"Authorization": "Bearer secret-token"}
    assert "secret-token" not in str(kwargs["params"])
    assert kwargs["params"] == {"dataset": "TaiwanStockPrice", "data_id": "2330", "start_date": "2026-09-01"}


@pytest.mark.unit
def test_finmind_quota_is_unavailable_and_starts_a_cooldown(monkeypatch):
    monkeypatch.delenv("FINMIND_API_TOKEN", raising=False)
    spent = _response(402, {"msg": "Requests reach the upper limit.", "status": 402})
    with mock.patch.object(finmind.requests, "get", return_value=spent) as get, \
            pytest.raises(VendorUnavailableError, match="FINMIND_API_TOKEN"):
        finmind.fetch_dataset("TaiwanStockInfo")
        # Within the cool-down FinMind is not asked again.
        with pytest.raises(VendorUnavailableError, match="skipping FinMind"):
            finmind.fetch_dataset("TaiwanStockPrice", data_id="2330")
    assert get.call_count == 1


@pytest.mark.unit
def test_finmind_quota_in_the_body_counts_too():
    # FinMind has answered 200 with the quota status in the body.
    quota = _response(200, {"msg": "upper limit", "status": 402})
    with mock.patch.object(finmind.requests, "get", return_value=quota), pytest.raises(VendorUnavailableError):
        finmind.fetch_dataset("TaiwanStockInfo")


@pytest.mark.unit
def test_finmind_sponsor_dataset_is_not_configured():
    sponsor_only = _response(400, {"msg": "Your level is Free, please update.", "status": 400})
    with mock.patch.object(finmind.requests, "get", return_value=sponsor_only), \
            pytest.raises(VendorNotConfiguredError, match="membership level"):
        finmind.fetch_dataset("TaiwanStockHoldingSharesPer", data_id="2330")


@pytest.mark.unit
def test_finmind_transport_errors_are_unavailable():
    with mock.patch.object(finmind.requests, "get", side_effect=requests.ConnectionError("reset")), \
            pytest.raises(VendorUnavailableError, match="ConnectionError"):
        finmind.fetch_dataset("TaiwanStockInfo")


@pytest.mark.unit
def test_finmind_caches_on_disk_when_asked():
    payload = {"status": 200, "msg": "success", "data": [{"stock_id": "2330"}]}
    with mock.patch.object(finmind.requests, "get", return_value=_response(payload=payload)) as get:
        first = finmind.fetch_dataset("TaiwanStockInfo", data_id="cache-test", ttl_seconds=math.inf)
        second = finmind.fetch_dataset("TaiwanStockInfo", data_id="cache-test", ttl_seconds=math.inf)
    assert first == second == payload["data"]
    assert get.call_count == 1


# --- TWSE / TPEx -----------------------------------------------------------

SECURITY_PAGE = (
    "<html><body>因為安全性考量，您所執行的頁面無法呈現。<BR>"
    "FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED.<BR></body></html>"
)


@pytest.mark.unit
def test_twse_returns_json_with_a_browser_style_user_agent():
    data = {"stat": "OK", "data": [["115/09/01", "31,855,287"]]}
    with mock.patch.object(twse.requests, "get", return_value=_response(payload=data)) as get:
        assert twse.fetch_json("https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY", {"stockNo": "2330"}) == data
    assert get.call_args.kwargs["headers"]["User-Agent"].startswith("Mozilla/5.0")


@pytest.mark.unit
def test_twse_security_page_is_an_outage_not_data():
    page = _response(200, payload=None, text=SECURITY_PAGE, content_type="text/html")
    with mock.patch.object(twse.requests, "get", return_value=page) as get:
        with pytest.raises(VendorUnavailableError, match="security page"):
            twse.fetch_json("https://openapi.twse.com.tw/v1/opendata/t187ap03_L")
        # The blocked host is left alone for a while; another host is not.
        with pytest.raises(VendorUnavailableError, match="leaving it alone"):
            twse.fetch_json("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL")
        assert get.call_count == 1
        with pytest.raises(VendorUnavailableError, match="security page"):
            twse.fetch_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes")
        assert get.call_count == 2


@pytest.mark.unit
@pytest.mark.parametrize("failure", [
    requests.ConnectionError("Connection reset by peer"),
    requests.Timeout("timed out"),
])
def test_twse_transport_errors_are_unavailable(failure):
    with mock.patch.object(twse.requests, "get", side_effect=failure), \
            pytest.raises(VendorUnavailableError):
        twse.fetch_json("https://www.twse.com.tw/rwd/zh/fund/T86")


@pytest.mark.unit
def test_twse_http_error_and_non_json_are_unavailable():
    with mock.patch.object(twse.requests, "get", return_value=_response(503, payload={})), \
            pytest.raises(VendorUnavailableError, match="503"):
        twse.fetch_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes")
    with mock.patch.object(twse.requests, "get", return_value=_response(200, payload=None, text="oops")), \
            pytest.raises(VendorUnavailableError, match="not JSON"):
        twse.fetch_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes")


@pytest.mark.unit
def test_twse_spaces_requests_per_host(monkeypatch):
    clock = [100.0]
    slept = []
    monkeypatch.setattr(twse.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(twse.time, "sleep", slept.append)

    twse._wait_turn("www.twse.com.tw")
    twse._wait_turn("www.twse.com.tw")
    twse._wait_turn("www.tpex.org.tw")   # another host keeps its own spacing
    twse._wait_turn("www.twse.com.tw")

    assert slept == [twse.MIN_INTERVAL_SECONDS, 2 * twse.MIN_INTERVAL_SECONDS]
