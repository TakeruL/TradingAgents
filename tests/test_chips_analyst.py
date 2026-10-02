"""The chips analyst: Taiwan chip data in, a report out, and that report in front of
the debaters; nothing at all for other instruments."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cli import display
from cli.models import AnalystType, AssetType
from cli.prefs import sanitize
from cli.prompts import filter_analysts_for_asset_type, parse_analysts
from tests.test_graph_end_to_end import (  # noqa: F401
    TEXT,
    TRADE_DATE,
    ScriptedModel,
    _graph,
    offline,
)
from tradingagents.agents.analysts import chips_analyst
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from tradingagents.agents.risk_mgmt.conservative_debator import create_conservative_debator
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.graph.analyst_execution import ANALYST_NODE_SPECS
from tradingagents.reporting import write_report_tree

CHIP_TOOLS = {"get_institutional_flows", "get_margin_short", "get_foreign_holding",
              "get_shareholding_distribution", "get_tw_market_overview"}


@pytest.mark.unit
def test_the_spec_runs_the_analysts_own_tools():
    spec = ANALYST_NODE_SPECS["chips"]
    assert (spec.agent_node, spec.report_key) == ("Chips Analyst", "chips_report")
    assert spec.tools is chips_analyst.TOOLS
    assert CHIP_TOOLS | {"get_stock_data"} == {t.name for t in spec.tools}


@pytest.mark.unit
def test_a_taiwan_run_reads_the_chip_data(tmp_path, monkeypatch, offline):  # noqa: F811
    graph = _graph(tmp_path, monkeypatch, ScriptedModel())

    state, signal = graph.propagate("2330.TW", TRADE_DATE)

    assert state["chips_report"] == TEXT
    assert offline >= CHIP_TOOLS
    assert signal == "Overweight"


@pytest.mark.unit
def test_another_instrument_gets_a_note_and_no_model_call():
    llm = MagicMock()
    node = chips_analyst.create_chips_analyst(llm)

    out = node({"company_of_interest": "AAPL", "trade_date": TRADE_DATE, "messages": []})

    assert "not applicable" in out["chips_report"] and "AAPL" in out["chips_report"]
    llm.bind_tools.assert_not_called()
    llm.invoke.assert_not_called()


@pytest.mark.unit
def test_a_us_run_calls_no_chip_tool(tmp_path, monkeypatch, offline):  # noqa: F811
    graph = _graph(tmp_path, monkeypatch, ScriptedModel())

    state, _ = graph.propagate("NVDA", TRADE_DATE)

    assert "not applicable" in state["chips_report"]
    assert not CHIP_TOOLS & offline


# --- the report reaches the debaters --------------------------------------------

def _state(ticker):
    return {
        "company_of_interest": ticker, "asset_type": "stock", "trade_date": TRADE_DATE,
        "market_report": "m", "sentiment_report": "s", "news_report": "n",
        "fundamentals_report": "f", "chips_report": "FOREIGN BUYING 5 DAYS",
        "trader_investment_plan": "plan",
        "investment_debate_state": {"history": "", "bull_history": "", "bear_history": "",
                                    "current_response": "", "count": 0},
        "risk_debate_state": {"history": "", "aggressive_history": "", "conservative_history": "",
                              "neutral_history": "", "current_aggressive_response": "",
                              "current_conservative_response": "", "current_neutral_response": "",
                              "count": 0},
    }


def _prompt(factory, state):
    captured = {}
    llm = MagicMock()
    llm.invoke.side_effect = lambda prompt: captured.setdefault("prompt", prompt) and MagicMock(content="x")
    factory(llm)(state)
    return captured["prompt"]


DEBATERS = [create_bull_researcher, create_bear_researcher, create_aggressive_debator,
            create_conservative_debator, create_neutral_debator]


@pytest.mark.unit
@pytest.mark.parametrize("factory", DEBATERS)
def test_debaters_read_the_chips_report_for_a_taiwan_listing(factory):
    prompt = _prompt(factory, _state("2330.TW"))
    assert "(chips) report: FOREIGN BUYING 5 DAYS" in prompt


@pytest.mark.unit
@pytest.mark.parametrize("factory", DEBATERS)
def test_debaters_prompts_for_other_instruments_are_unchanged(factory):
    state = _state("AAPL")
    with_report = _prompt(factory, state)
    state.pop("chips_report")
    assert with_report == _prompt(factory, state)
    assert "chips" not in with_report


@pytest.mark.unit
def test_a_missing_chips_report_reads_as_absent():
    state = _state("2330.TW")
    state["chips_report"] = ""
    assert "(No chips report in this run" in _prompt(create_bull_researcher, state)


@pytest.mark.unit
def test_the_report_tree_holds_the_chips_report(tmp_path):
    path = write_report_tree({"chips_report": "chips findings"}, "2330.TW", tmp_path)
    assert (tmp_path / "1_analysts" / "chips.md").read_text(encoding="utf-8") == "chips findings"
    assert "### Chips Analyst" in path.read_text(encoding="utf-8")


# --- CLI ----------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("ticker,offered", [
    ("2330.TW", True), ("6488.TWO", True), ("AAPL", False), (None, True),
])
def test_the_chips_analyst_is_offered_for_taiwan_listings(ticker, offered):
    available = filter_analysts_for_asset_type(list(AnalystType), AssetType.STOCK, ticker)
    assert (AnalystType.CHIPS in available) is offered


@pytest.mark.unit
def test_crypto_has_no_chips_analyst():
    assert AnalystType.CHIPS not in filter_analysts_for_asset_type(list(AnalystType), AssetType.CRYPTO)


@pytest.mark.unit
def test_naming_the_chips_analyst_for_a_us_ticker_is_refused():
    assert parse_analysts("market,chips", AssetType.STOCK, "2330.TW") == [AnalystType.MARKET, AnalystType.CHIPS]
    with pytest.raises(ValueError, match="chips is not available for AAPL"):
        parse_analysts("market,chips", AssetType.STOCK, "AAPL")


@pytest.mark.unit
def test_a_remembered_chips_choice_is_dropped_for_a_us_ticker():
    prefs = {"analysts": ["market", "chips"]}
    assert sanitize(prefs, "stock", "AAPL")["analysts"] == ["market"]
    assert sanitize(prefs, "stock", "2330.TW")["analysts"] == ["market", "chips"]


@pytest.mark.unit
def test_the_display_tracks_the_chips_analyst():
    assert display.ANALYST_AGENT_NAMES["chips"] == "Chips Analyst"
    assert display.ANALYST_REPORT_MAP["chips"] == "chips_report"
    assert "chips" in display.ANALYST_ORDER
    assert display.MessageBuffer.REPORT_SECTIONS["chips_report"] == ("chips", "Chips Analyst")
