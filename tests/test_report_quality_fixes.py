"""Fixes from a real Taiwan run: reports cut off mid-sentence, a news analyst with
no Taiwan macro tool, and dividend-adjusted prices read as a change of scale."""

from __future__ import annotations

import warnings
from unittest import mock

import pandas as pd
import pytest

from tradingagents.agents.analysts import news_analyst
from tradingagents.agents.context import taiwan_guidance
from tradingagents.agents.tools import get_tw_market_overview
from tradingagents.dataflows.vendors.yahoo import market
from tradingagents.llm_clients import anthropic_client
from tradingagents.llm_clients.anthropic_client import AnthropicClient


def _max_tokens(model, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return AnthropicClient(model, api_key="x", **kwargs).get_llm().max_tokens


@pytest.mark.unit
def test_a_current_model_without_a_profile_is_not_capped_at_4096():
    # As langchain-anthropic 1.7.4 does for claude-sonnet-5-5: no profile, 4,096 tokens.
    with mock.patch("langchain_anthropic.chat_models._get_default_model_profile", return_value={}):
        assert _max_tokens("claude-sonnet-5-5") == anthropic_client._CURRENT_MODEL_MAX_TOKENS
        assert _max_tokens("claude-sonnet-5-5", max_tokens=2000) == 2000
        assert _max_tokens("claude-3-haiku-20240307") == 4096


@pytest.mark.unit
def test_a_profiled_model_keeps_its_own_limit():
    assert _max_tokens("claude-opus-5-5") >= anthropic_client._CURRENT_MODEL_MAX_TOKENS


@pytest.mark.unit
def test_the_news_analyst_reads_the_taiwan_market_overview():
    assert get_tw_market_overview in news_analyst.TOOLS
    assert "get_tw_market_overview" in taiwan_guidance("news", "2330.TW")


def _history(*_args, **_kwargs):
    index = pd.DatetimeIndex(["2026-07-29", "2026-07-30"], name="Date")
    return pd.DataFrame({"Open": [5100.0, 5600.0], "High": [5200.0, 5700.0], "Low": [5000.0, 5500.0],
                         "Close": [5110.01, 5620.0], "Volume": [1, 1], "Dividends": [0.0, 64.99]},
                        index=index)


@pytest.mark.unit
@pytest.mark.parametrize("symbol,noted", [("7769.TW", True), ("AAPL", False)])
def test_taiwan_prices_say_they_are_dividend_adjusted(symbol, noted):
    ticker = mock.Mock(history=_history)
    with mock.patch.object(market.yf, "Ticker", return_value=ticker), \
            mock.patch.object(market, "fill_tw_closes", side_effect=lambda d, s: d), \
            mock.patch.object(market, "_assert_ohlcv_not_stale"):
        out = market.get_YFin_data_online(symbol, "2026-07-29", "2026-07-30")
    assert ("dividend-adjusted" in out) is noted
    assert "5620.0" in out
