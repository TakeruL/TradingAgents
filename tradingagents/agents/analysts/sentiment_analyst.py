"""Sentiment analyst: one sentiment report from three sources.

The node fetches its sources before calling the model and puts them in the
prompt, so the model reports on data it was given rather than inventing posts:

  1. News headlines: Yahoo Finance
  2. StockTwits messages: the cashtag stream, with Bullish/Bearish tags
  3. Reddit posts: r/wallstreetbets, r/stocks, r/investing

Each source is trimmed to the analysis window. With a TypeSafe key, the social
posts are screened by Jev first (see post_screen). These feeds serve recent items
and are not archived, so a historical run's sentiment inputs are not
point-in-time.

The report is a SentimentReport through structured output where the provider
supports it and free text otherwise, so the band, score and confidence header
reads the same across providers.
"""

from datetime import datetime, timedelta

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.context import (
    get_instrument_context_from_state,
    get_language_instruction,
    resolve_instrument_identity,
)
from tradingagents.agents.post_screen import jev_screen
from tradingagents.agents.schemas import SentimentReport, render_sentiment_report
from tradingagents.agents.structured import (
    NO_EXTERNAL_TOOLS,
    bind_structured,
    invoke_structured_or_freetext,
)
from tradingagents.agents.tools import get_news
from tradingagents.dataflows.symbols import taiwan_listing, tw_stock_id
from tradingagents.dataflows.vendors.google_news_tw import fetch_google_news_tw
from tradingagents.dataflows.vendors.ptt import fetch_ptt_posts
from tradingagents.dataflows.vendors.reddit import fetch_reddit_posts
from tradingagents.dataflows.vendors.stocktwits import fetch_stocktwits_messages


def _seven_days_back(trade_date: str) -> str:
    return (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")


def create_sentiment_analyst(llm):
    """Create a sentiment analyst node for the trading graph.

    Pre-fetches news + StockTwits + Reddit data, injects them into the
    prompt as structured blocks, and produces a deterministic sentiment
    report via structured output (with a free-text fallback for providers
    that do not support it).
    """
    structured_llm = bind_structured(llm, SentimentReport, "Sentiment Analyst")

    def sentiment_analyst_node(state):
        ticker = state["company_of_interest"]
        end_date = state["trade_date"]
        start_date = _seven_days_back(end_date)
        instrument_context = get_instrument_context_from_state(state)

        # Pre-fetch all three sources. Each fetcher degrades gracefully and
        # returns a string (no exceptions surface from here), so the LLM
        # always sees something — either real data or a clear placeholder.
        news_block = get_news.func(ticker, start_date, end_date)
        # Pass the analysis window so a historical run trims social posts to it
        # instead of leaking today's chatter into a backtest (#1220).
        screen = jev_screen(ticker)
        if taiwan_listing(ticker):
            # StockTwits and Reddit barely cover Taiwan listings; Taiwan's own
            # forum and press do.
            system_message = _taiwan_system_message(ticker, start_date, end_date, news_block, screen)
        else:
            stocktwits_block = fetch_stocktwits_messages(
                ticker, limit=30, start_date=start_date, end_date=end_date, screen=screen
            )
            reddit_block = fetch_reddit_posts(ticker, start_date=start_date, end_date=end_date, screen=screen)

            system_message = _build_system_message(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                news_block=news_block,
                stocktwits_block=stocktwits_block,
                reddit_block=reddit_block,
            )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Report what your tools support; another agent decides the trade."
                    # No tool-calling here: the data is pre-fetched into the
                    # prompt, so tool-range wording would only invite a
                    # hallucinated tool call (#1130).
                    " Today's date is {current_date}; treat it as 'now' for all analysis. {instrument_context}"
                    " " + NO_EXTERNAL_TOOLS +
                    "\n{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=end_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        # Format the template into a concrete message list so the structured
        # and free-text paths receive the same input. No bind_tools — the
        # data is already in the prompt.
        formatted_messages = prompt.format_messages(messages=state["messages"])

        report_text = invoke_structured_or_freetext(
            structured_llm,
            llm,
            formatted_messages,
            render_sentiment_report,
            "Sentiment Analyst",
        )

        return {
            "messages": [AIMessage(content=report_text)],
            "sentiment_report": report_text,
        }

    return sentiment_analyst_node


def _build_system_message(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    news_block: str,
    stocktwits_block: str,
    reddit_block: str,
) -> str:
    """Assemble the sentiment-analyst system message with structured data blocks."""
    return f"""You are a financial market sentiment analyst. Your task is to produce a comprehensive sentiment report for {ticker} covering the period from {start_date} to {end_date}, drawing on three complementary data sources that have already been collected for you.

## Data sources (pre-fetched, in this prompt)

### News headlines — Yahoo Finance, past 7 days
Institutional framing. Fact-driven, slower-moving signal.

<start_of_news>
{news_block}
<end_of_news>

### StockTwits messages — retail-trader social platform indexed by cashtag
Fast-moving signal. Each message carries a user-labeled sentiment tag (Bullish / Bearish / no-label) plus the message body.

<start_of_stocktwits>
{stocktwits_block}
<end_of_stocktwits>

### Reddit posts — r/wallstreetbets, r/stocks, r/investing (past 7 days)
Community discussion, without vote or comment counts. Subreddit character matters (r/wallstreetbets is often contrarian/exuberant; r/stocks more measured; r/investing longer-term).

<start_of_reddit>
{reddit_block}
<end_of_reddit>

## How to analyze this data (best practices)

1. **Read the StockTwits Bullish/Bearish ratio as a leading retail-sentiment signal.** A 70/30 bullish/bearish split is moderately bullish; ≥90/10 may indicate over-extension and contrarian risk; 50/50 is uncertainty. Sample size matters — base rates on the actual message count, not percentages alone. A block headed "Screened by Jev" has had off-topic posts removed; its stance count is a classifier's read of every on-topic post fetched, labelled or not, of which the posts listed are a sample. Read it alongside the user tags.

2. **Look for cross-source divergences.** If news framing is bearish but StockTwits is overwhelmingly bullish, that mismatch is itself a signal — it can mean retail is leaning into a thesis the news flow hasn't caught up to (or vice versa, that retail is chasing while institutions are cautious).

3. **Read Reddit posts for substance.** The feed carries no vote or comment counts, so judge a post by its body excerpt, not its title alone, and do not infer engagement.

4. **Distinguish opinion from event.** A news headline ("Nvidia announces $500M Corning deal") is an event; a StockTwits post ("buying NVDA, this is going to moon") is opinion. Both are inputs but should be weighted differently in your conclusions.

5. **Identify recurring narrative themes.** What topic keeps coming up across sources? That's the dominant narrative driving current sentiment.

6. **Be honest about data limits.** If StockTwits returned only a handful of messages, or one or more sources returned an "<unavailable>" placeholder, the sentiment read is less robust — flag this explicitly in the `confidence` field and the narrative. If the sources are silent on a given subreddit, say so.

7. **Identify catalysts and risks** that emerge across sources — news of upcoming earnings, product launches, competitive threats, macro headlines, etc.

8. **Past sentiment is not predictive.** Frame your conclusions as signal for the trader to weigh alongside fundamentals and technicals, not as a price call.

{_OUTPUT_FIELDS}{get_language_instruction()}"""



def _taiwan_system_message(ticker, start_date, end_date, news_block, screen) -> str:
    """The sentiment brief for a Taiwan listing: its own press and its retail forum."""
    stock_id = tw_stock_id(ticker)
    name = resolve_instrument_identity(ticker).get("company_name")
    media_block = fetch_google_news_tw(name or stock_id, start_date=start_date, end_date=end_date)
    ptt_block = fetch_ptt_posts(stock_id, name, start_date=start_date, end_date=end_date, screen=screen)
    label = f"{name} ({ticker})" if name else ticker
    return f"""You are a financial market sentiment analyst covering the Taiwan stock market. Your task is to produce a comprehensive sentiment report for {label} covering the period from {start_date} to {end_date}, drawing on three complementary sources that have already been collected for you. The sources are in Traditional Chinese; read them in full.

## Data sources (pre-fetched, in this prompt)

### Company news — Taiwan financial news by stock code (FinMind), past 7 days
Reporting tied to this stock. Items whose source is CMoney are posts on its 股市爆料同學會 forum: read them as retail opinion, not press.

<start_of_news>
{news_block}
<end_of_news>

### Press coverage — Google News, Taiwan edition (經濟日報, 工商時報, 鉅亨網, 自由財經, Yahoo 股市 …)
How the Taiwan financial press frames the company: headline count is a gauge of attention, headline tone a gauge of institutional framing.

<start_of_media>
{media_block}
<end_of_media>

### Retail discussion — PTT Stock board (批踢踢 Stock 版)
Taiwan's busiest retail stock forum. Post titles carry a category tag: [標的] is a trading pick that ends in 多 (long) or 空 (short); [新聞] reposts news; [情報] reposts company filings; [心得] and [請益] are experience and questions. Replies are tagged 推 (agree), 噓 (disagree) or → (comment); the list score is the net of 推 over 噓 (爆 is 100 or more; X marks net disagreement).

<start_of_ptt>
{ptt_block}
<end_of_ptt>

## How to analyze this data (best practices)

1. **Read [標的] picks as declared retail positioning** (a long or short call with its reasoning), and weigh each by its replies: a pick with many 噓 is a pick the board rejects.

2. **Read 推/噓 counts as crowd agreement, and reply volume as attention.** A news repost with hundreds of replies is a story retail is reacting to; read its 推/噓 split for the reaction's direction.

3. **Treat crowded optimism with suspicion.** PTT Stock has a well-known contrarian streak ("反指標"): when the board is uniformly euphoric about a stock, retail is likely already positioned. Unanimous gloom can mark capitulation the same way.

4. **Look for divergences between press and forum.** Bullish press with a skeptical board, or the reverse, is itself a signal.

5. **Distinguish opinion from event.** A [情報] filing or [新聞] report is an event; a [標的] pick or reply is opinion. Weigh them differently.

6. **Identify recurring themes, catalysts and risks** across sources: monthly revenue, earnings calls (法說會), ex-dividend dates, attention or disposition notices, export controls, geopolitics.

7. **Be honest about data limits.** A source that returned an "<unavailable>" placeholder or only a few posts makes the read less robust — say so in the `confidence` field and the narrative.

8. **Past sentiment is not predictive.** Frame your conclusions as signal for the trader to weigh alongside fundamentals, chips and technicals, not as a price call.

{_OUTPUT_FIELDS}

{get_language_instruction()}"""


_OUTPUT_FIELDS = """## Output fields

Fill the following fields:

- **overall_band**: Exactly one of Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish. Use Mixed when sources point in clearly different directions; Neutral only when all sources are genuinely silent.
- **overall_score**: A number from 0 (maximally bearish) to 10 (maximally bullish); 5 is neutral. Keep it consistent with overall_band.
- **confidence**: low / medium / high, based on data quality and sample size.
- **narrative**: Full source-by-source breakdown, divergences, dominant narrative themes, catalysts and risks, and a markdown summary table of key sentiment signals (direction, source, supporting evidence).

"""
