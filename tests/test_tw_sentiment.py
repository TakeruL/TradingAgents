"""Taiwan sentiment sources: the PTT Stock board and Google News (zh-TW), and the
sentiment analyst reading them for Taiwan listings in place of StockTwits/Reddit.

HTML and RSS fixtures are trimmed copies of real pages; no test reaches the network.
"""

from __future__ import annotations

from unittest import mock

import pytest
import requests

from tests.test_taiwan_prompts import CaptureModel
from tradingagents.agents import context
from tradingagents.agents.analysts import sentiment_analyst
from tradingagents.dataflows.vendors import google_news_tw, ptt


@pytest.fixture(autouse=True)
def _google_news_uncached(monkeypatch):
    """Each test reads its own feed: no disk cache, no pacing or retry pause."""
    monkeypatch.setattr(google_news_tw, "cached_json", lambda namespace, key, ttl, fetch: fetch())
    monkeypatch.setattr(google_news_tw, "MIN_INTERVAL", 0)
    monkeypatch.setattr(google_news_tw, "RETRY_DELAY", 0)

# 1790943882 = 2026-10-02 12:24:42 UTC; 1790770000 = 2026-09-30; 1780000000 = 2026-05-28.
SEARCH_PAGE = """<div class="r-list-container action-bar-margin bbs-screen">
<div class="r-ent">
  <div class="nrec"><span class="hl f2">1</span></div>
  <div class="title"><a href="/bbs/Stock/M.1790943882.A.49A.html">[標的] 2330 台積電 多</a></div>
  <div class="meta"><div class="author">PolarBearCat</div><div class="date">10/02</div></div>
  <div class="mark"></div>
</div>
<div class="r-ent">
  <div class="nrec"><span class="hl f1">爆</span></div>
  <div class="title"><a href="/bbs/Stock/M.1790770000.A.1B2.html">[新聞] 台積電傳美德州蓋新廠</a></div>
  <div class="meta"><div class="author">newsbot</div><div class="date">9/30</div></div>
  <div class="mark"></div>
</div>
<div class="r-ent">
  <div class="nrec"><span class="hl f1">X2</span></div>
  <div class="title">(本文已被刪除) [someone]</div>
  <div class="meta"><div class="author">-</div><div class="date">9/30</div></div>
</div>
<div class="r-ent">
  <div class="nrec"><span class="hl f3">X1</span></div>
  <div class="title"><a href="/bbs/Stock/M.1780000000.A.333.html">[標的] 2330 台積電 空</a></div>
  <div class="meta"><div class="author">bear</div><div class="date">5/28</div></div>
</div>
</div>"""

POST_PAGE = """<div id="main-container">
<div id="main-content" class="bbs-screen bbs-content"><div class="article-metaline"><span class="article-meta-tag">作者</span><span class="article-meta-value">PolarBearCat</span></div><div class="article-metaline-right"><span class="article-meta-tag">看板</span><span class="article-meta-value">Stock</span></div><div class="article-metaline"><span class="article-meta-tag">標題</span><span class="article-meta-value">[標的] 2330 台積電 多</span></div>
原文標題： 請勿刪減或自創標題，違者4-1處分，此行請刪除
基本面真的沒什麼好挑的
AI 需求持續強
--
※ 發信站: 批踢踢實業坊(ptt.cc)
<div class="push"><span class="hl push-tag">推 </span><span class="push-userid">a</span><span class="push-content">: 讚</span></div>
<div class="push"><span class="hl push-tag">推 </span><span class="push-userid">b</span><span class="push-content">: 讚</span></div>
<div class="push"><span class="f1 hl push-tag">噓 </span><span class="push-userid">c</span><span class="push-content">: AI寫的</span></div>
<div class="push"><span class="f1 hl push-tag">→ </span><span class="push-userid">d</span><span class="push-content">: 再看看</span></div>
</div>
<script>window.dataLayer = window.dataLayer || [];</script>
</div>"""


@pytest.mark.unit
def test_search_page_rows_are_dated_by_their_post_id():
    posts = ptt.parse_search_page(SEARCH_PAGE)
    assert [p["title"] for p in posts] == ["[標的] 2330 台積電 多", "[新聞] 台積電傳美德州蓋新廠", "[標的] 2330 台積電 空"]
    assert [p["score"] for p in posts] == [1, 100, -10]
    assert posts[0]["posted"].strftime("%Y-%m-%d") == "2026-10-02"
    assert posts[0]["url"] == "https://www.ptt.cc/bbs/Stock/M.1790943882.A.49A.html"


@pytest.mark.unit
def test_post_page_body_and_reply_tags():
    post = ptt.parse_post_page(POST_PAGE)
    assert post["body"] == "基本面真的沒什麼好挑的 AI 需求持續強 --"
    assert (post["push"], post["boo"], post["neutral"]) == (2, 1, 1)
    assert "dataLayer" not in post["body"] and "請勿" not in post["body"]


@pytest.mark.unit
def test_stance_is_read_from_pick_titles_only():
    assert ptt.stance("[標的] 2330 台積電 多") == "多"
    assert ptt.stance("[標的] 6405 悅城 空") == "空"
    assert ptt.stance("[新聞] 台積電 多頭") is None


def _board(pages: dict):
    """A ``_get`` stand-in: search pages by (term, page), post pages by URL."""
    def get(url, params=None):
        if params:
            return pages.get((params["q"], params["page"]), "")
        return pages.get(url)
    return get


@pytest.mark.unit
def test_posts_are_trimmed_to_the_window_and_merged_across_terms():
    pages = {("2330", 1): SEARCH_PAGE, ("台積電", 1): SEARCH_PAGE,
             "https://www.ptt.cc/bbs/Stock/M.1790943882.A.49A.html": POST_PAGE}
    with mock.patch.object(ptt, "_get", side_effect=_board(pages)):
        out = ptt.fetch_ptt_posts("2330", "台積電", start_date="2026-09-26", end_date="2026-10-02")
    assert out.startswith("PTT Stock board — 2 posts about 台積電 (2330)")
    assert "多 (long): 1, 空 (short): 0" in out
    assert "[2026-10-02] [標的] 2330 台積電 多 (list score +1; replies 推 2 / 噓 1 / → 1)" in out
    assert "body excerpt: 基本面真的沒什麼好挑的" in out
    assert "空" not in out.split("\n", 1)[1]   # the May pick is outside the window


@pytest.mark.unit
def test_a_window_the_search_never_reached_is_unavailable_not_empty():
    # Every page is full (20 posts) and recent: three pages never reach March.
    page = ('<div class="r-ent"><div class="nrec"></div><div class="title">'
            '<a href="/bbs/Stock/M.1790943882.A.49A.html">x</a></div></div>') * 20
    with mock.patch.object(ptt, "_get", side_effect=_board({("2330", p): page for p in (1, 2, 3)})):
        out = ptt.fetch_ptt_posts("2330", None, start_date="2026-03-01", end_date="2026-03-07")
    assert out.startswith("<PTT unavailable for 2026-03-01..2026-03-07")


@pytest.mark.unit
def test_a_failed_search_is_unavailable_and_a_covered_empty_window_is_empty():
    with mock.patch.object(ptt, "_get", return_value=None):
        assert ptt.fetch_ptt_posts("2330", "台積電", start_date="2026-09-26", end_date="2026-10-02") \
            .startswith("<PTT unavailable: the board search failed")
    with mock.patch.object(ptt, "_get", side_effect=_board({("2330", 1): SEARCH_PAGE})):
        out = ptt.fetch_ptt_posts("2330", None, start_date="2026-07-01", end_date="2026-07-07")
    assert out == "<no PTT Stock posts about 2330 within 2026-07-01..2026-07-07>"


@pytest.mark.unit
def test_screening_drops_off_topic_posts():
    def screen(texts):
        return [t.startswith("[標的]") for t in texts], "Screened: 1 of 2 on topic."

    with mock.patch.object(ptt, "_get", side_effect=_board({("2330", 1): SEARCH_PAGE})):
        out = ptt.fetch_ptt_posts("2330", None, start_date="2026-09-26", end_date="2026-10-02", screen=screen)
    assert out.startswith("Screened: 1 of 2 on topic.\nPTT Stock board — 1 posts")


RSS = """<?xml version="1.0" encoding="UTF-8"?><rss><channel>
<item><title>台積電法說10/15登場 - Yahoo新聞</title><pubDate>Fri, 02 Oct 2026 08:00:00 GMT</pubDate><source url="x">Yahoo新聞</source></item>
<item><title>台積電法說10/15登場 - Yahoo新聞</title><pubDate>Fri, 02 Oct 2026 09:00:00 GMT</pubDate><source url="x">Yahoo新聞</source></item>
<item><title>台積電2奈米擴產 - 經濟日報</title><pubDate>Thu, 01 Oct 2026 01:00:00 GMT</pubDate><source url="x">經濟日報</source></item>
<item><title>舊聞 - 工商時報</title><pubDate>Mon, 01 Jun 2026 01:00:00 GMT</pubDate><source url="x">工商時報</source></item>
</channel></rss>"""


@pytest.mark.unit
def test_google_news_headlines_are_windowed_and_deduplicated():
    response = mock.Mock(content=RSS.encode("utf-8"))
    response.raise_for_status.return_value = None
    with mock.patch.object(google_news_tw.requests, "get", return_value=response) as get:
        out = google_news_tw.fetch_google_news_tw("台積電", start_date="2026-09-26", end_date="2026-10-02")
    params = get.call_args.kwargs["params"]
    assert params["q"] == "台積電 after:2026-09-26 before:2026-10-03" and params["ceid"] == "TW:zh-Hant"
    assert out.splitlines() == [
        "Google News (zh-TW) — 2 of 2 headlines about 台積電 within 2026-09-26..2026-10-02:",
        "  [2026-10-02] 台積電法說10/15登場 (source: Yahoo新聞)",
        "  [2026-10-01] 台積電2奈米擴產 (source: 經濟日報)",
    ]


@pytest.mark.unit
def test_google_news_failure_is_unavailable():
    with mock.patch.object(google_news_tw.requests, "get", side_effect=requests.ConnectionError("reset")):
        out = google_news_tw.fetch_google_news_tw("台積電", start_date="2026-09-26", end_date="2026-10-02")
    assert out.startswith("<Google News unavailable")


@pytest.mark.unit
def test_google_news_retries_a_503_once():
    ok = mock.Mock(content=RSS.encode("utf-8"))
    ok.raise_for_status.return_value = None
    busy = mock.Mock()
    busy.raise_for_status.side_effect = requests.HTTPError("503")
    with mock.patch.object(google_news_tw.requests, "get", side_effect=[busy, ok]):
        found = google_news_tw.search_google_news_tw("台積電", start_date="2026-09-26", end_date="2026-10-02")
    assert [title for _, title, _ in found] == ["台積電法說10/15登場", "台積電2奈米擴產"]


def _feeds(by_query):
    """requests.get stand-in answering each Taiwan topic with its own items."""
    def get(url, params, **kwargs):
        query = params["q"].split(" after:")[0]
        if by_query.get(query) is None:
            raise requests.ConnectionError("503")
        items = "".join(
            f"<item><title>{t}</title><pubDate>Thu, 22 Oct 2026 01:00:00 GMT</pubDate>"
            f"<source url='x'>經濟日報</source></item>" for t in by_query[query])
        response = mock.Mock(content=f"<rss><channel>{items}</channel></rss>".encode())
        response.raise_for_status.return_value = None
        return response
    return get


@pytest.mark.unit
def test_global_news_puts_taiwan_macro_topics_first(monkeypatch):
    config = {"market": "tw", "global_news_lookback_days": 7, "global_news_article_limit": 10,
              "tw_global_news_queries": ["新台幣 匯率", "央行 利率", "台海"],
              "tw_global_news_article_limit": 6}
    monkeypatch.setattr(google_news_tw, "get_config", lambda: config)
    monkeypatch.setattr(google_news_tw, "get_global_news_yfinance", lambda *a: "<yahoo headlines>")
    feeds = {"新台幣 匯率": ["新台幣貶2分", "新台幣失守32.6", "匯市一", "匯市二"],
             "央行 利率": ["央行理監事會將開", "新台幣貶2分"], "台海": None}
    with mock.patch.object(google_news_tw.requests, "get", side_effect=_feeds(feeds)):
        out = google_news_tw.get_global_news_tw("2026-10-23")
    taiwan, international = out.split("## International news (Yahoo Finance)")
    # Two headlines per topic (6 over 3 topics), each headline once.
    assert taiwan.count("新台幣貶2分") == 1 and "匯市一" not in taiwan
    assert "### 央行 利率" in taiwan and "央行理監事會將開" in taiwan
    assert "<1 of 3 topics could not be read" in taiwan
    assert international.strip() == "<yahoo headlines>"


@pytest.mark.unit
def test_global_news_is_yahoos_alone_outside_the_taiwan_mode(monkeypatch):
    monkeypatch.setattr(google_news_tw, "get_config", lambda: {"market": "us"})
    monkeypatch.setattr(google_news_tw, "get_global_news_yfinance", lambda *a: "<yahoo headlines>")
    with mock.patch.object(google_news_tw.requests, "get", side_effect=AssertionError("no Google call")):
        assert google_news_tw.get_global_news_tw("2026-10-23") == "<yahoo headlines>"


@pytest.mark.unit
def test_global_news_falls_through_when_google_is_unreachable(monkeypatch):
    config = {"market": "tw", "global_news_lookback_days": 7, "global_news_article_limit": 10,
              "tw_global_news_queries": ["台海"]}
    monkeypatch.setattr(google_news_tw, "get_config", lambda: config)
    with mock.patch.object(google_news_tw.requests, "get", side_effect=requests.ConnectionError("503")), \
            pytest.raises(google_news_tw.VendorUnavailableError):
        google_news_tw.get_global_news_tw("2026-10-23")


# --- the sentiment analyst ----------------------------------------------------

@pytest.fixture
def sources(monkeypatch):
    calls = []
    for name in ("fetch_ptt_posts", "fetch_google_news_tw", "fetch_stocktwits_messages", "fetch_reddit_posts"):
        monkeypatch.setattr(sentiment_analyst, name,
                            lambda *a, _n=name, **k: calls.append((_n, a, k)) or f"<{_n} block>")
    monkeypatch.setattr(sentiment_analyst.get_news, "func", lambda *a: "<news block>")
    monkeypatch.setattr(sentiment_analyst, "resolve_instrument_identity",
                        lambda t: {"company_name": "台積電"} if t.endswith(".TW") else {})
    context._identity.cache_clear()
    return calls


def _run(ticker):
    model = CaptureModel()
    sentiment_analyst.create_sentiment_analyst(model)(
        {"company_of_interest": ticker, "trade_date": "2026-10-02", "messages": []})
    return model.seen[-1]


@pytest.mark.unit
def test_a_taiwan_listing_reads_ptt_and_the_taiwan_press(sources):
    prompt = _run("2330.TW")
    used = [name for name, _, _ in sources]
    assert used == ["fetch_google_news_tw", "fetch_ptt_posts"]
    assert sources[0][1] == ("台積電",) and sources[1][1] == ("2330", "台積電")
    assert sources[1][2]["start_date"] == "2026-09-25"
    for block in ("<news block>", "<fetch_google_news_tw block>", "<fetch_ptt_posts block>", "反指標"):
        assert block in prompt
    assert "StockTwits" not in prompt and "overall_band" in prompt


@pytest.mark.unit
def test_other_instruments_keep_stocktwits_and_reddit(sources):
    prompt = _run("AAPL")
    assert [name for name, _, _ in sources] == ["fetch_stocktwits_messages", "fetch_reddit_posts"]
    assert "PTT" not in prompt and "<fetch_reddit_posts block>" in prompt
