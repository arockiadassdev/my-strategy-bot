# 🤖 my-strategy-bot

**BTC/USDT EMA 9/21 Crossover Trading Bot** — Backtest engine, paper trading, live trading, and Streamlit dashboard.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 📋 Strategy

| Parameter | Value |
|-----------|-------|
| **Asset** | BTC/USDT |
| **Timeframe** | Daily candles only |
| **Entry** | 9 EMA crosses **above** 21 EMA → long, 100% capital |
| **Exit** | 9 EMA crosses **below** 21 EMA → flat |
| **Leverage** | None (long-only) |
| **Commission** | 0.1% per side |
| **Fill** | Next bar open |
| **Starting Capital** | $100,000 |

## 🚀 Quick Start

```bash
# 1. Clone & enter
git clone https://github.com/arockiadassdev/my-strategy-bot.git
cd my-strategy-bot

# 2. Setup
python setup.py

# 3. Run backtest
python main.py --backfill

# 4. Launch dashboard
streamlit run app.py
```

## 📊 Backtest Results (3 years BTC/USDT Daily)

```
Period:           2023-07-17 → 2026-07-15 (3.0 years)
Initial Capital:  $100,000.00
Final Equity:     $276,109.13  (+176.11%)
Strategy CAGR:    40.32%
Buy & Hold CAGR:  29.30%
Total Trades:     22
Win Rate:         40.91%
Profit Factor:    3.40
Max Drawdown:     27.24%
```

### Validation
- ✅ **Trade count**: 22 — sufficient for statistical relevance
- ✅ **Plateau check**: Robust — only 5.00pp variation across 8/20 and 10/22
- 🥇 **Verdict**: WORTH TRADING

## 🎮 CLI Modes

| Command | Description |
|---------|-------------|
| `python main.py --backfill` | Full backtest + validation + verification gate |
| `python main.py --paper` | Paper trading with simulated fills |
| `python main.py --testnet` | Bybit testnet (requires API keys) |
| `python main.py --live` | Live trading (safety gates enforced) |

## 🖥️ Streamlit Dashboard

```bash
streamlit run app.py
```

Opens at **http://localhost:8501** with 3 tabs:

1. **Backtest** — Trade list, candlestick chart with EMAs, equity curve, validation checks, verdict
2. **Live Signals** — Auto-refreshing BTC/USDT price monitor with EMA cross detection
3. **About** — Architecture documentation

## 🏗️ Architecture

```
my-strategy-bot/
├── app.py                    # Streamlit dashboard
├── main.py                   # CLI entrypoint
├── config.py                 # Config loader + mode validation
├── setup.py                  # Setup script
├── paper_loop.py             # Paper trading loop
├── requirements.txt          # Dependencies
├── .env.example              # Config template
├── data/
│   └── provider.py           # Bybit public API OHLCV fetcher
├── signals/
│   └── ema_cross.py          # EMA crossover detection
├── backtest/
│   ├── engine.py             # Replay engine (fill-on-next-open)
│   ├── trade_list.py         # Trade records + P&L calc
│   └── stats.py              # Win rate, profit factor, max DD, CAGR
├── validation/
│   └── checks.py             # Trade count, plateau, regime, verdict
├── execution/
│   ├── base.py               # Abstract exchange interface
│   ├── simulator.py          # Paper fills
│   ├── bybit_testnet.py      # Bybit testnet API
│   └── bybit_live.py         # Bybit live API (safety gates)
├── state/
│   └── sqlite_state.py       # SQLite position tracking
├── alerts/
│   └── telegram.py           # Telegram notifications
└── safety/
    └── checks.py             # API key validation, scam detection
```

## 🔒 Safety Rails

| Rail | Enforcement |
|------|-------------|
| **MAX_CAPITAL** | Bot sizes from config — never reads live account balance |
| **API key permissions** | Warns to verify trade-only + IP-whitelist + no withdrawals |
| **Scam detection** | `reject_deposit_scam_pattern()` scans all config for "deposit", "send funds", "activate account" |
| **One position max** | SQLite state prevents double-entry across restarts |
| **No blind retries** | Any unexpected API error → log + Telegram alert + halt |
| **Live mode gate** | Refuses start unless `MAX_CAPITAL > 0` and API keys are set |

## ⚙️ Configuration

Copy `.env.example` to `.env` and set:

```env
MODE=paper
BYBIT_API_KEY=
BYBIT_API_SECRET=
MAX_CAPITAL=0
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
BACKTEST_DAYS=1095
```

## 📦 Dependencies

- `requests` — Bybit API calls
- `numpy` — Numerical operations
- `pandas` — Data manipulation
- `python-dotenv` — Environment config
- `streamlit` — Dashboard UI
- `plotly` — Interactive charts

## 📝 Verification Gate

To cross-check backtest results against TradingView:

1. Open TradingView, symbol BTCUSDT, daily timeframe
2. Apply indicators: EMA 9, EMA 21 on close
3. Entry: EMA 9 crosses **above** EMA 21 → enter **next day at open**
4. Exit: EMA 9 crosses **below** EMA 21 → exit **next day at open**
5. Commission: 0.1% per side

> ⚠️ **Discrepancy risk**: First ~30 bars may differ slightly due to EMA seed value differences between pandas `ewm()` and TradingView's SMA-based initialization. Focus verification on trades after bar 30+.

## 📄 License

MIT