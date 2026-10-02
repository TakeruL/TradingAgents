<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>
<br>
<div align="center">
  <a href="https://github.com/TauricResearch" target="_blank"><img alt="TradingAgents #1 Repository of the Day" src="https://trendshift.io/api/badge/repositories/16192" width="250" height="55"/></a>
</div>
<br>
<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents: Multi-Agents LLM Financial Trading Framework

## News

<!-- news:start -->
- [2026-09] **TradingAgents v0.5.2** released with parallel analysts for a faster analysis, a CLI that runs without prompts from flags such as `--ticker` and `--date`, the run's settings recorded in every report, and backtests that see only data published by each analysis date.
- [2026-09] **TradingAgents v0.5.1** released with a package layout organised by what each module holds (import paths moved), optional Jev screening of social posts, GPT-6 Sol and Luna as the default models, and fixes to run isolation and SEC EDGAR statements.
- [2026-09] **TradingAgents v0.5.0** released with point-in-time integrity across every dated path, SEC EDGAR fundamentals served as filed, backtesting over a ticker and date grid, portfolio-aware runs, and current model lineups across every provider.

Full release notes are in [CHANGELOG.md](CHANGELOG.md).

<details>
<summary>Earlier news</summary>

- [2026-08] **TradingAgents v0.4.0** released with look-ahead / point-in-time fixes across FRED macro, social sentiment, and the decision-log memory; clearer decision signals; working CLI checkpoint resume; Trader price grounding; and the GPT-5.6 and GLM-5.3 models.
- [2026-07] **TradingAgents v0.3.1** released with correctness and stability fixes: Alpha Vantage look-ahead filtering, graph-router crash-safety, graph-shape-aware checkpoint resume, working crypto sentiment sources, a configurable LLM retry budget, Bedrock API-key auth, and Claude Sonnet 5 / Fable 5 support.
- [2026-06] **TradingAgents v0.3.0** released with a verified data-access contract, an expanded provider registry (NVIDIA, Kimi, Groq, Mistral, Bedrock, and any OpenAI-compatible endpoint), FRED and Polymarket data vendors, a current-generation model catalog, and a CI gate.
- [2026-05] **TradingAgents v0.2.5** released with the grounded Sentiment Analyst, GPT-5.5 etc. model coverage, Qwen/GLM/MiniMax dual-region support, `TRADINGAGENTS_*` env-var configurability with API-key auto-detection, remote Ollama support, non-US alpha benchmarks, and ticker path-traversal hardening.
- [2026-04] **TradingAgents v0.2.4** released with structured-output agents (Research Manager, Trader, Portfolio Manager), LangGraph checkpoint resume, persistent decision log, DeepSeek/Qwen/GLM/Azure provider support, Docker, and a Windows UTF-8 encoding fix.
- [2026-03] **TradingAgents v0.2.3** released with multi-language support, GPT-5.4 family models, unified model catalog, backtesting date fidelity, and proxy support.
- [2026-03] **TradingAgents v0.2.2** released with GPT-5.4/Gemini 3.1/Claude 4.6 model coverage, five-tier rating scale, OpenAI Responses API, Anthropic effort control, and cross-platform stability.
- [2026-02] **TradingAgents v0.2.0** released with multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x) and improved system architecture.
- [2026-01] **Trading-R1** [Technical Report](https://arxiv.org/abs/2509.11420) released, with [Terminal](https://github.com/TauricResearch/Trading-R1) expected to land soon.

</details>
<!-- news:end -->

<div align="center">

🚀 [TradingAgents](#tradingagents-framework) | ⚡ [Installation & CLI](#installation-and-cli) | 🎬 [Demo](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [Package Usage](#tradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Citation](#citation)

</div>

> 🎉 **TradingAgents** officially released! We have received numerous inquiries about the work, and we would like to express our thanks for the enthusiasm in our community.
>
> So we decided to fully open-source the framework. Looking forward to building impactful projects with you!

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. By deploying specialized LLM-powered agents: from fundamental analysts, sentiment experts, and technical analysts, to trader, risk management team, the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents framework is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. [It is not intended as financial, investment, or trading advice.](https://tauric.ai/disclaimer/)

Our framework decomposes complex trading tasks into specialized roles.

### Analyst Team
- Fundamentals Analyst: Evaluates company financials and performance metrics, identifying intrinsic values and potential red flags.
- Sentiment Analyst: Aggregates news headlines, StockTwits, and Reddit chatter into a single sentiment read to gauge short-term market mood. For Taiwan stocks it reads the PTT Stock board and the Taiwan financial press instead.
- News Analyst: Monitors global news and macroeconomic indicators, interpreting the impact of events on market conditions.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) to detect trading patterns and forecast price movements.
- Chips Analyst (Taiwan stocks only): Reads institutional investors' net buying, margin and short balances, foreign ownership and holder concentration, the "chip" data Taiwan traders weigh alongside price and fundamentals.

The selected analysts work at the same time, each on its own tools, and the research debate starts once all of their reports are in.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions, determining the timing and magnitude of trades.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## Installation and CLI

### Installation

Clone TradingAgents:
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

TradingAgents needs Python 3.11 or later. Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.13
conda activate tradingagents
```

Or with [uv](https://docs.astral.sh/uv/):
```bash
uv venv --python 3.13
source .venv/bin/activate
```

Install the package and its dependencies (`uv pip install .` with uv):
```bash
pip install .
```

### Docker

Alternatively, run with Docker:
```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

After updating the repository, rebuild the image with `docker compose build`.

Results, reports, the memory log and the cache live in the `tradingagents_data` volume. To keep them in a folder on the host instead, create the folder and point `TRADINGAGENTS_DATA_DIR` at it, in `.env` or the shell: `mkdir -p data && TRADINGAGENTS_DATA_DIR=./data docker compose run --rm tradingagents`.

For local models with Ollama:
```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required APIs

TradingAgents supports multiple LLM providers. Set the API key for your chosen provider:

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen (international, dashscope-intl.aliyuncs.com)
export DASHSCOPE_CN_API_KEY=...    # Qwen (China, dashscope.aliyuncs.com)
export ZHIPU_API_KEY=...           # GLM via Z.AI (international)
export ZHIPU_CN_API_KEY=...        # GLM via BigModel (China, open.bigmodel.cn)
export MINIMAX_API_KEY=...         # MiniMax (global, api.minimax.io)
export MINIMAX_CN_API_KEY=...      # MiniMax (China, api.minimaxi.com)
export OPENROUTER_API_KEY=...      # OpenRouter
export MISTRAL_API_KEY=...         # Mistral
export MOONSHOT_API_KEY=...        # Kimi (Moonshot)
export GROQ_API_KEY=...            # Groq
export NVIDIA_API_KEY=...          # NVIDIA NIM
export FRED_API_KEY=...            # FRED macro data (free, optional)
export FINMIND_API_TOKEN=...       # FinMind Taiwan market data (free, optional; raises the quota)
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
export TYPESAFE_API_KEY=...        # Jev social-post screening (optional)
```

For Azure OpenAI, copy `.env.enterprise.example` to `.env.enterprise` and fill in your credentials.

For AWS Bedrock, install the extra with `pip install ".[bedrock]"`, set `llm_provider: "bedrock"`, configure AWS credentials (environment variables, `~/.aws/credentials`, or an IAM role) and `AWS_DEFAULT_REGION`, and use a Bedrock model ID, e.g. `us.anthropic.claude-opus-5-5`.

For local models, configure Ollama with `llm_provider: "ollama"`. The default endpoint is `http://localhost:11434/v1`; set `OLLAMA_BASE_URL` to point at a remote `ollama-serve`. Pull models with `ollama pull <name>`, and pick "Custom model ID" in the CLI for any model not listed by default.

For any other OpenAI-compatible server (vLLM, LM Studio, llama.cpp, or a custom relay), use `llm_provider: "openai_compatible"` and set the endpoint via `backend_url` (or `TRADINGAGENTS_LLM_BACKEND_URL`), e.g. `http://localhost:8000/v1` for vLLM or `http://localhost:1234/v1` for LM Studio. The model is whatever your server serves. No key is needed for local servers; set `OPENAI_COMPATIBLE_API_KEY` when the endpoint requires one.

With `TYPESAFE_API_KEY` set, the Sentiment Analyst screens StockTwits and Reddit posts with TypeSafe's Jev before reading them. Posts that are not about the company are dropped, and each source opens with a count of the remaining posts by stance: bullish, bearish, neutral, or unclear. Without the key, posts pass through unscreened. `jev-latest` moves with new releases; set `TYPESAFE_DEFAULT_MODEL` to a versioned ID such as `jev-1.13.0` to hold it fixed across runs.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```
You will see a screen where you can select your desired tickers, analysis date, LLM provider, research depth, and more. Your previous run's answers come back as the defaults, so pressing Enter accepts them. The `TRADINGAGENTS_*` variables in `.env` still skip their step entirely.

To run without questions, for a scheduled job or a script, answer the per-run steps with flags and the rest with `TRADINGAGENTS_*` variables:
```bash
export TRADINGAGENTS_LLM_PROVIDER=openai TRADINGAGENTS_QUICK_THINK_LLM=gpt-6-luna TRADINGAGENTS_DEEP_THINK_LLM=gpt-6-sol
export TRADINGAGENTS_OUTPUT_LANGUAGE=English TRADINGAGENTS_MAX_DEBATE_ROUNDS=1 TRADINGAGENTS_MAX_RISK_ROUNDS=1
tradingagents --ticker NVDA --date 2026-09-23 --analysts market,news,fundamentals --save --no-show
```
Each flag skips only its own question. Run without a terminal, a missing answer stops the run before it starts and names the flag or variable to set.

### Markets and tickers

TradingAgents works with any market Yahoo Finance covers, using the exchange-suffixed ticker. Company identity and the alpha benchmark resolve automatically per market.

- US: `AAPL`, `SPY`
- Hong Kong: `0700.HK` · Tokyo: `7203.T` · London: `AZN.L`
- India: `RELIANCE.NS`, `.BO` · Canada: `.TO` · Australia: `.AX`
- China A-shares: Shanghai `.SS`, Shenzhen `.SZ` (e.g. `600519.SS` for Kweichow Moutai)
- Crypto: `BTC-USD`, `ETH-USD`
- Taiwan: `2330.TW` (TWSE), `6488.TWO` (TPEx), or simply `2330` / `台積電`, which resolve to the right exchange. See [台股分析（Taiwan stocks）](#台股分析taiwan-stocks).

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## 台股分析（Taiwan stocks）

這個版本預設以台股為主：輸入股票代號或中文名稱即可分析，資料改用台股自己的來源，報告預設以繁體中文撰寫。美股、港股、加密貨幣照常可用。

### 快速開始

```bash
cp .env.example .env      # 填入你使用的 LLM 金鑰，例如 OPENAI_API_KEY
tradingagents             # 輸入 2330、台積電、6488 或 6488.TWO
```

- **代號與名稱**：`2330`、`台積電` 會轉成 `2330.TW`；上櫃股如 `6488`、`環球晶` 會轉成 `6488.TWO`。查詢順序是 FinMind 股票清單，再來是證交所／櫃買中心的公司名單；都查不到時，純數字代號當成上市股（`.TW`）。中文名稱對不到或對到好幾檔時，會列出候選股請你改輸入代號。
- **FinMind token（選填）**：第一次分析台股時，CLI 會請你貼上 token 並存進 `.env`；直接按 Enter 可略過，改用免費額度，之後不會再問。也可以自己在 `.env` 設定 `FINMIND_API_TOKEN`。免費註冊：https://finmindtrade.com/
- **不經互動執行**（排程或腳本）：

  ```bash
  tradingagents --ticker 2330 --date 2026-09-30 --analysts market,sentiment,news,fundamentals,chips --save --no-show
  ```

- **在程式中呼叫**：

  ```python
  from tradingagents.default_config import DEFAULT_CONFIG
  from tradingagents.graph.trading_graph import TradingAgentsGraph

  ta = TradingAgentsGraph(config=DEFAULT_CONFIG.copy())   # 預設五位分析師，含籌碼分析師
  state, decision = ta.propagate("2330", "2026-09-30")    # 也可傳 "台積電" 或 "2330.TW"
  ta.save_reports(state, "2330.TW")
  ```

### 市場模式與報告語言

| 設定 | 預設 | 說明 |
|---|---|---|
| `TRADINGAGENTS_MARKET` | `tw` | `tw`：純數字代號與中文名稱視為台股並自動查詢；`us`：代號照輸入使用。帶後綴的代號（`AAPL`、`0700.HK`、`2330.TW`）在兩種模式都可用。 |
| `TRADINGAGENTS_OUTPUT_LANGUAGE` | `Traditional Chinese (繁體中文)` | 報告語言。評級行（`**Rating**:`）與 `FINAL TRANSACTION PROPOSAL:` 固定保留英文，供程式判讀。 |

要回到原本以美股為主的行為：`TRADINGAGENTS_MARKET=us`、`TRADINGAGENTS_OUTPUT_LANGUAGE=English`。

### 資料來源

台股（`.TW`／`.TWO`）的資料依序由 FinMind、證交所／櫃買中心官方資料、Yahoo Finance 提供；FinMind 免費額度用完時自動改用官方資料。其他標的完全不經過這兩個來源，也不會多發任何請求。

| 資料 | 來源 | 時間點規則（回測不會看到未來資料） |
|---|---|---|
| 股價 | Yahoo Finance → FinMind → 證交所／櫃買 | 只到分析日 |
| 三大財報 | FinMind | 法定公告期限過後才算公開：Q1 5/15、Q2 8/14（金融業 8/31）、Q3 11/14、年報隔年 3/31。損益為單季，現金流量為年初至今累計 |
| 月營收（MoM、YoY、累計 YoY） | FinMind → 官方 OpenAPI | FinMind 記錄的公布日或次月 10 日；官方資料只有最新一個月，分析日早於應公布日時不提供 |
| 本益比、淨值比、殖利率、股利 | FinMind → 證交所／櫃買 | 只到分析日；股利以公告日為準 |
| 三大法人買賣超 | FinMind → 證交所 T86／櫃買 | 只到分析日 |
| 融資融券、券資比、融資使用率 | FinMind → 證交所 MI_MARGN／櫃買 | 只到分析日 |
| 外資持股比例 | FinMind | 只到分析日 |
| 集保股權分散（大戶持股） | FinMind（需付費方案） | 每週，只到分析日 |
| 大盤：加權指數、法人與融資、外資台指期淨未平倉、美元兌台幣 | FinMind → 證交所 | 只到分析日 |
| 個股新聞（含 CMoney 爆料同學會貼文） | FinMind | 分析期間內 |
| 媒體標題（經濟日報、工商時報、鉅亨網…） | Google 新聞台灣版 | 用 `after:`／`before:` 限定分析期間 |
| 散戶討論 | PTT Stock 版 | 依文章 ID 中的發文時間篩選；搜尋只涵蓋近期，較早的回測區間標示為「無法取得」 |

### 台股專屬的分析師行為

- **籌碼分析師（Chips Analyst）**：分析三大法人連買連賣與 5／10／20 日合計、融資融券與券資比、外資持股、集保大戶持股、大盤法人與台指期部位，並和股價對照（例如融資增價跌代表籌碼凌亂）。只有分析台股時才會出現在 CLI 選單；報告存成 `1_analysts/chips.md`，並提供給多空研究員與風險分析師。
- **所有角色**都會知道台股規則：±10% 漲跌幅、T+2 交割、1 張 = 1,000 股與零股、現股當沖、注意股與處置股、除權息與填息、月營收公布時程。
- **市場分析師**：判讀漲跌停、成交量換算為張、分辨除息缺口與賣壓。
- **基本面分析師**：優先看月營收，再看三率、EPS、本益比與淨值比在一年區間的位置、股利。
- **新聞分析師**：讀中文新聞，並關注 Fed 與美債殖利率、半導體／AI 景氣、新台幣與外資、台灣央行、外銷訂單、美中與兩岸情勢。
- **情緒分析師**：改讀 PTT Stock 版、Google 新聞台灣版與 FinMind 新聞，不再使用 StockTwits／Reddit；會統計 `[標的]` 文的多空表態與推噓數，並留意 PTT 的「反指標」傾向。
- **交易員與投資組合經理**：以張或零股計算部位，並考慮跌停鎖死時停損單可能成交不了的風險。

### FinMind 額度與官方資料備援

- FinMind 不帶 token 時，每個 IP 每小時只有數百次請求；共用網路（例如雲端環境）很快就會用完，建議申請免費 token。
- 額度用完後，FinMind 會暫停 10 分鐘不再發送請求，期間自動改用證交所／櫃買官方資料；已過去的交易日資料會永久快取在 `~/.tradingagents/cache`。
- 證交所對請求頻率有限制，有時也會封鎖雲端主機的 IP，此時會出現「因為安全性考量」頁面。程式把這種情況當成暫時無法取得資料，5 分鐘內不再請求，分析照常進行。

### 需要開放的網域

在有網路白名單的環境（沙盒、公司防火牆）執行時，台股功能需要以下網域：

| 網域 | 用途 |
|---|---|
| `api.finmindtrade.com` | FinMind 主要資料源 |
| `openapi.twse.com.tw`、`www.twse.com.tw` | 證交所 OpenAPI 與依日期查詢的報表 |
| `www.tpex.org.tw` | 櫃買中心 OpenAPI 與報表 |
| `www.ptt.cc` | PTT Stock 版 |
| `news.google.com` | Google 新聞台灣版 |
| `query1.finance.yahoo.com`、`query2.finance.yahoo.com`、`fc.yahoo.com` | Yahoo Finance 股價與技術指標 |
| `api.stlouisfed.org` | FRED 美國總經數據（選用，需 `FRED_API_KEY`） |

另外需要你所使用的 LLM 供應商的網域，例如 `api.openai.com`。

### 已知限制

- 集保股權分散需要 FinMind 付費方案；免費版會標示為「無法取得」，分析照常進行。
- 官方 OpenAPI 大多只提供最新一期資料：月營收只有最新一個月；三大財報沒有官方備援，FinMind 無法使用時會退回 Yahoo Finance（回測日期不提供）。
- 官方備援的逐日資料一次最多取 10 個交易日，以免請求過多被封鎖。
- PTT 搜尋只涵蓋近期文章，較早的回測區間會標示為「無法取得」，不會當成「沒有討論」。
- FinMind 新聞一次只能查一天，每次分析最多查 10 天。
- CMoney 股市爆料同學會的個股討論串只能透過其內部 API（需要從網頁取得訪客 token）讀取；這不是公開介面，且有使用條款疑慮，因此沒有直接串接。FinMind 新聞已收錄部分爆料同學會的貼文。

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen (Alibaba DashScope, international and China endpoints), GLM (Zhipu), MiniMax (global + China), OpenRouter, Ollama for local models, and Azure OpenAI for enterprise.

### Python Usage

To use TradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
state, decision = ta.propagate("NVDA", "2026-09-01")
print(decision)

# the same report tree the CLI saves, under results_dir/reports
ta.save_reports(state, "NVDA")
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # e.g. openai, google, anthropic, deepseek, groq, ollama; openai_compatible covers any OpenAI-compatible endpoint (vLLM, LM Studio, llama.cpp, ...)
config["deep_think_llm"] = "gpt-6-sol"    # Model for complex reasoning
config["quick_think_llm"] = "gpt-6-luna"   # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-09-01")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

### Fundamentals as filed

US company statements come from SEC EDGAR, which records the date every figure was filed. A run dated in the past reads the statements exactly as they stood that day: a fiscal year that has ended but has not been filed yet is not served, and a figure restated later still reads as first reported. Apple's 2008 total assets were filed as $39.6B and restated to $36.2B in 2010, so a run dated in between reads $39.6B. EDGAR needs no account or API key.

Other companies' statements (outside the US and Taiwan) come from Yahoo Finance, which dates a statement by the period it covers rather than by when it was published. A run dated today reads them; a run dated in the past is told they are withheld, since Yahoo cannot say which figures were public by then.

Insider trades are dated by when they happened, not when they were filed, so a run dated in the past is told they are withheld as well.

SEC asks callers to identify themselves and refuses requests that carry no contact address, so a default one is sent. Set your own so SEC can reach you rather than the project:

```bash
SEC_EDGAR_USER_AGENT="Your Name your@email.com"
```

It covers companies that file with the SEC, including foreign companies listed in the US. Anything else, such as Hong Kong or A-share listings, falls through to the next vendor in the chain. EDGAR's machine-readable filings begin in 2009, and a fourth quarter is reported as unavailable rather than derived, because filers publish it only inside the annual figure.

Taiwan companies' statements come from FinMind, dated by the period they cover; a run reads a period only once its statutory filing deadline has passed (Q1 May 15, Q2 August 14 or August 31 for financials, Q3 November 14, the annual report March 31), and monthly revenue once it was published or due on the 10th of the following month.

### Current holdings

By default the agents do not know what you hold, so their guidance is written for a reader who applies it to their own position. Pass a portfolio to have the trader, the risk analysts and the portfolio manager work against your actual book.

```python
from tradingagents.portfolio import PortfolioContext

portfolio = PortfolioContext.model_validate({
    "cash": 25000.0,
    "currency": "USD",
    "positions": [{"ticker": "NVDA", "quantity": 120, "average_price": 150.0}],
})
_, decision = ta.propagate("NVDA", "2026-09-01", portfolio=portfolio)
```

The CLI takes the same content as a JSON file: `tradingagents --portfolio my_book.json`.

An empty `positions` list means a flat book, which is different from passing nothing. A run without a portfolio is never treated as flat.

## Persistence and Recovery

TradingAgents persists two kinds of state across runs.

### Memory log

The memory log is always on. Each completed run appends its decision to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, TradingAgents fetches the realised return (raw, and alpha against the instrument's regional benchmark), generates a one-paragraph reflection, and injects the most recent same-ticker decisions plus recent cross-ticker lessons into the Portfolio Manager prompt, so each analysis carries forward what worked and what didn't.

Override the path with `TRADINGAGENTS_MEMORY_LOG_PATH`.

### Checkpoint resume

Checkpoint resume is opt-in via `--checkpoint`. When enabled, LangGraph saves state after each node so a crashed or interrupted run resumes from the last successful step instead of starting over. The run view says whether it resumed a saved run or started fresh. Checkpoints are cleared automatically on successful completion.

Per-ticker SQLite databases live at `~/.tradingagents/cache/checkpoints/<TICKER>.db` (override the base with `TRADINGAGENTS_CACHE_DIR`). Use `--clear-checkpoints` to reset all of them before a run.

```bash
tradingagents --checkpoint           # enable for this run
tradingagents --clear-checkpoints    # reset before running
```

```python
config = DEFAULT_CONFIG.copy()
config["checkpoint_enabled"] = True
ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("NVDA", "2026-09-01")
```

## Evaluating decisions over time

One run gives one decision, which cannot tell you whether the system decides well. `run_backtest` runs the same pipeline over a grid of tickers and dates, writes to a memory log of its own, and scores the decisions whose holding window has since traded.

```python
from tradingagents.backtest import iter_grid, run_backtest, summarize

dates = iter_grid("2026-06-01", "2026-08-01", every_n_days=7)
result = run_backtest(["NVDA", "AAPL"], dates, config, selected_analysts=["market", "news"])
print(summarize(result).render())
```

From the CLI:

```bash
tradingagents backtest NVDA,AAPL --start 2026-06-01 --end 2026-08-01 --every 7
```

Each cell is scored on realized alpha against the instrument's regional benchmark, grouped by rating. Your own memory log is never written to, and re-running the same grid with `run_id=result.run_id` skips the cells that already ran, so an interrupted sweep continues where it stopped.

## Reproducibility

TradingAgents is LLM-driven, so two runs of the same ticker and date can differ. This is expected for a research tool built on language models, not a defect. The variation comes from a few distinct sources, and it helps to separate them.

Language model sampling is non-deterministic. Even at a fixed temperature, providers do not guarantee byte-identical output across calls, and reasoning models (the default GPT-6 family, and any thinking-mode model) vary the most because their internal reasoning is itself sampled.

Live data moves. News, StockTwits, and Reddit return different content as time passes, so a run today sees different inputs than a run last week even for the same historical trade date. Pin the analysis date to hold the price and indicator window fixed, but the social and news sources still reflect "now".

To reduce variation you can lower the sampling temperature. Set `temperature` in your config (or `TRADINGAGENTS_TEMPERATURE` in `.env`); lower values make models that honor it more repeatable. The current curated models are reasoning-first and largely ignore temperature, so for tighter reproducibility name a non-reasoning model in your config, or in `TRADINGAGENTS_DEEP_THINK_LLM` and `TRADINGAGENTS_QUICK_THINK_LLM`. Any model ID your provider serves is accepted, whether or not the picker lists it.

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["temperature"] = 0.0
# Reasoning models ignore temperature. For tighter reproducibility, name a
# non-reasoning model in deep_think_llm / quick_think_llm.
```

What does not vary anymore: the analyzed company identity is resolved deterministically from the ticker before any agent runs, and the market analyst grounds exact price and indicator claims in a verified data snapshot. Earlier reports of "different companies" or fabricated price levels across runs are addressed by these two mechanisms.

Backtest results are not guaranteed to match any published figure. Returns depend on the model, the temperature, the date range, data quality, and the sampling above. Treat the framework as a research scaffold for studying multi-agent analysis, not as a strategy with a fixed, replicable return.

## Contributing

Contributions are welcome: bug fixes, documentation, and feature ideas; past contributions are credited per release in [`CHANGELOG.md`](CHANGELOG.md).

## Citation

Please reference our work if you find *TradingAgents* provides you with some help :)

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
