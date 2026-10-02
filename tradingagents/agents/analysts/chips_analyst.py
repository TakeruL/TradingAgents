"""Chips analyst (籌碼分析): who is buying a Taiwan stock, on what credit, and who holds it.

Taiwan's exchanges publish, every trading day, what the three institutional
investor groups bought and sold in each stock, and how much of it is held on
margin or sold short; TDCC publishes weekly how the shares are spread across
holders. Taiwan traders read this "chip" data alongside price and fundamentals,
so it gets its own analyst. Any other instrument has no such data: the node
answers with a note and makes no model call.
"""

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.analysts.turn import take_turn
from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.tools import (
    get_foreign_holding,
    get_institutional_flows,
    get_margin_short,
    get_shareholding_distribution,
    get_stock_data,
    get_tw_market_overview,
)
from tradingagents.dataflows.symbols import taiwan_listing

# The tools this analyst is offered; its tool node is built from the same tuple.
TOOLS = (
    get_institutional_flows,
    get_margin_short,
    get_foreign_holding,
    get_shareholding_distribution,
    get_tw_market_overview,
    get_stock_data,
)

GUIDE = """You are a chips analyst (籌碼分析師) for the Taiwan stock market. Chip data shows who is buying and selling the stock, how much of it is held on credit, and how concentrated its holders are. Write a report on what the chip data says about the stock's supply and demand over roughly the past month.

Gather the data with your tools:
- get_institutional_flows: daily net buying by the three institutional investor groups (三大法人) in lots, with streaks and 5/10/20-day totals.
- get_margin_short: margin purchase (融資) and short sale (融券) balances, the short/margin ratio (券資比) and margin utilization (融資使用率).
- get_foreign_holding: the foreign ownership ratio (外資持股比例) and the room left under the foreign ownership limit.
- get_shareholding_distribution: the weekly TDCC distribution (集保股權分散): the share held by holders of more than 400 / 1,000 lots.
- get_tw_market_overview: the market backdrop: TAIEX, market-wide institutional flows and margin, foreign net open interest in TAIEX futures, USD/TWD.
- get_stock_data: daily prices, to read the chip moves against price.

How to read it:
- Foreign investors (外資) move large caps; read their direction together with the TAIEX futures positioning and the TWD (foreign selling with a weakening TWD is capital leaving). Investment trusts (投信) carry more signal in small and mid caps: a run of consecutive trust buying is notable, and quarter-end window dressing (季底作帳) can inflate it. Dealer hedging (自營商避險) mostly offsets warrant positions and says little about direction.
- Margin up while the price falls means chips are scattering into retail hands (籌碼凌亂), a bearish sign; margin down while the price rises means chips are settling (籌碼沉澱). High margin utilization raises the risk of forced selling (斷頭) in a decline.
- A high short/margin ratio (券資比) sets up a possible short squeeze (軋空), especially before a shareholders' meeting or ex-rights date, when short sellers must cover (融券強制回補).
- A rising foreign ownership ratio is accumulation; little room left under the limit caps further foreign buying.
- A rising share held by large holders (over 400 or 1,000 lots) with fewer holders overall means chips are concentrating in strong hands.
- Weigh agreement and disagreement between the groups, and between chips and price; say which way the balance tips and how strongly.

Report only what the tools return. When a tool answers DATA_UNAVAILABLE, NO_DATA_AVAILABLE or NOT_APPLICABLE, say that data is unavailable and do not estimate it. Provide specific, actionable insights with supporting evidence (dates, lots, percentages) to help traders make informed decisions."""


def not_taiwan_report(ticker: str) -> str:
    return (
        f"Chips analysis is not applicable: `{ticker}` is not a Taiwan-listed security, "
        "and institutional flow, margin and shareholding data is published for Taiwan "
        "listings (.TW / .TWO) only."
    )


def create_chips_analyst(llm):
    def chips_analyst_node(state):
        ticker = str(state["company_of_interest"])
        if not taiwan_listing(ticker):
            note = not_taiwan_report(ticker)
            return {"messages": [AIMessage(content=note)], "chips_report": note}

        current_date = state["trade_date"]
        system_message = (
            GUIDE
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " Report what your tools support; another agent decides the trade."
                    " You have access to the following tools: {tool_names}."
                    " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}\n"
                    "{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in TOOLS]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=get_instrument_context_from_state(state))

        result, report = take_turn(prompt, llm, TOOLS, state["messages"])

        return {
            "messages": [result],
            "chips_report": report,
        }

    return chips_analyst_node
