"""Taiwan listings get Taiwan's trading rules and role-specific guidance in every
prompt; every other instrument's prompts are exactly as before."""

from __future__ import annotations

from unittest import mock

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from tradingagents.agents import context
from tradingagents.agents.analysts import fundamentals_analyst, market_analyst, news_analyst
from tradingagents.agents.managers.portfolio_manager import create_portfolio_manager
from tradingagents.agents.tools import get_monthly_revenue
from tradingagents.agents.trader.trader import create_trader


class CaptureModel(BaseChatModel):
    """Answers with a fixed report and keeps every prompt it was sent."""

    seen: list = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "capture"

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        raise NotImplementedError

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append("\n".join(str(m.content) for m in messages))
        text = "Report.\n\n**Rating**: Hold\n\nFINAL TRANSACTION PROPOSAL: **HOLD**"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def _state(ticker):
    return {
        "company_of_interest": ticker, "asset_type": "stock", "trade_date": "2026-09-30",
        "messages": [], "market_report": "m", "investment_plan": "plan", "trader_investment_plan": "t",
        "risk_debate_state": {
            "history": "h", "aggressive_history": "", "conservative_history": "", "neutral_history": "",
            "latest_speaker": "", "current_aggressive_response": "", "current_conservative_response": "",
            "current_neutral_response": "", "count": 0,
        },
    }


def _prompt(factory, ticker):
    model = CaptureModel()
    factory(model)(_state(ticker))
    return model.seen[-1]


@pytest.mark.unit
def test_instrument_context_carries_the_taiwan_rules():
    tw = context.build_instrument_context("6488.TWO")
    for rule in ("TPEx OTC-traded", "±10%", "T+2", "lot (張) of 1,000 shares", "零股", "處置股", "填息"):
        assert rule in tw
    assert "Taiwan" not in context.build_instrument_context("AAPL")


@pytest.mark.unit
@pytest.mark.parametrize("factory,role_marker", [
    (market_analyst.create_market_analyst, "limit moves"),
    (fundamentals_analyst.create_fundamentals_analyst, "月營收"),
    (news_analyst.create_news_analyst, "Taiwan's central bank (CBC)"),
    (create_trader, "lots (張, 1,000 shares)"),
    (create_portfolio_manager, "lots (張, 1,000 shares)"),
])
def test_each_role_gets_its_taiwan_guidance(factory, role_marker):
    tw = _prompt(factory, "2330.TW")
    us = _prompt(factory, "AAPL")
    assert role_marker in tw and "±10%" in tw
    assert role_marker not in us and "Taiwan" not in us


@pytest.mark.unit
def test_guidance_is_empty_for_other_instruments():
    for role in ("market", "fundamentals", "news", "trading"):
        assert context.taiwan_guidance(role, "NVDA") == ""
        assert context.taiwan_guidance(role, "2330.TW").startswith(" For this Taiwan listing")


@pytest.mark.unit
def test_the_fundamentals_analyst_can_read_monthly_revenue():
    assert get_monthly_revenue in fundamentals_analyst.TOOLS


@pytest.mark.unit
def test_a_taiwan_listing_is_named_as_its_exchange_lists_it():
    context._identity.cache_clear()
    profile = {"stock_id": "2330", "name": "台積電", "listing": "twse", "industry": "半導體業"}
    with mock.patch.object(context, "stock_profile", return_value=profile), \
            mock.patch.object(context, "get_company_profile", side_effect=AssertionError("no Yahoo call")):
        identity = context.resolve_instrument_identity("2330.TW")
    assert identity == {"company_name": "台積電", "industry": "半導體業", "exchange": "TWSE (listed)"}
    assert "Company: 台積電" in context.build_instrument_context("2330.TW", identity=identity)
    context._identity.cache_clear()


@pytest.mark.unit
def test_yahoo_names_a_taiwan_listing_the_listing_does_not_know():
    context._identity.cache_clear()
    with mock.patch.object(context, "stock_profile", return_value=None), \
            mock.patch.object(context, "get_company_profile", return_value={"longName": "Some Co"}):
        assert context.resolve_instrument_identity("9999.TW")["company_name"] == "Some Co"
    context._identity.cache_clear()
