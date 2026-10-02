"""The CLI's offer to save a FinMind token before a Taiwan stock is looked up."""

import os
import sys
from unittest import mock

import pytest

import cli.prompts as prompts
from tradingagents.dataflows.config import run_config
from tradingagents.dataflows.tw_symbols import looks_taiwanese
from tradingagents.dataflows.vendors.finmind import common as finmind

ENV = prompts.FINMIND_TOKEN_ENV


def _answer(value):
    return mock.Mock(ask=mock.Mock(return_value=value))


@pytest.fixture(autouse=True)
def _no_quota_pause():
    finmind.reset_cooldown()
    yield
    finmind.reset_cooldown()


@pytest.fixture
def unset(monkeypatch, tmp_path):
    """No token in the environment, and a fresh project directory for .env."""
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.unit
@pytest.mark.parametrize("value,expected", [("tok-123", "tok-123"), ("", None)])
def test_a_present_variable_is_never_asked_about(monkeypatch, value, expected):
    # An empty value is an earlier "skip"; it is not asked again.
    monkeypatch.setenv(ENV, value)
    with mock.patch.object(prompts.questionary, "password") as password:
        assert prompts.ensure_finmind_token() == expected
    password.assert_not_called()


@pytest.mark.unit
def test_an_unattended_run_is_not_asked(unset, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with mock.patch.object(prompts.questionary, "password") as password:
        assert prompts.ensure_finmind_token() is None
    password.assert_not_called()
    assert not (unset / ".env").exists()


@pytest.mark.unit
def test_a_pasted_token_is_saved_owner_only_and_lifts_the_quota_pause(unset):
    finmind._start_cooldown()
    with mock.patch.object(prompts.questionary, "password", return_value=_answer("  tok-abc  ")):
        assert prompts.ensure_finmind_token() == "tok-abc"

    env_file = unset / ".env"
    assert "FINMIND_API_TOKEN='tok-abc'" in env_file.read_text()
    assert oct(env_file.stat().st_mode & 0o777) == oct(0o600)
    assert os.environ[ENV] == "tok-abc"
    finmind._check_cooldown()  # raises if the pause were still on


@pytest.mark.unit
@pytest.mark.parametrize("answer", ["", None])  # Enter, or Ctrl-C
def test_a_skip_is_recorded_so_the_next_run_does_not_ask(unset, answer):
    with mock.patch.object(prompts.questionary, "password", return_value=_answer(answer)):
        assert prompts.ensure_finmind_token() is None
    assert "FINMIND_API_TOKEN=''" in (unset / ".env").read_text()
    assert os.environ[ENV] == ""

    with mock.patch.object(prompts.questionary, "password") as password:
        assert prompts.ensure_finmind_token() is None
    password.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize("entry,asked", [
    ("2330", True),
    ("台積電", True),
    ("6488.TWO", True),
    ("AAPL", False),
    ("BTC-USD", False),
])
def test_get_ticker_offers_the_token_only_for_taiwan_entries(entry, asked):
    with mock.patch.object(prompts.questionary, "text", return_value=_answer(entry)), \
            mock.patch.object(prompts, "ensure_finmind_token") as ensure, \
            mock.patch.object(prompts, "normalize_ticker_symbol", side_effect=lambda t: t):
        prompts.get_ticker()
    assert ensure.called is asked


@pytest.mark.unit
@pytest.mark.parametrize("entry,market,expected", [
    ("2330.TW", "tw", True),
    ("6488.two", "us", True),     # a suffixed symbol is Taiwanese in any mode
    ("2330", "tw", True),
    ("00679B", "tw", True),
    ("環球晶", "tw", True),
    ("2330", "us", False),
    ("台積電", "us", False),
    ("AAPL", "tw", False),
    ("0700.HK", "tw", False),
    ("", "tw", False),
])
def test_looks_taiwanese(entry, market, expected):
    with run_config({"market": market}):
        assert looks_taiwanese(entry) is expected
