"""
Streamlit dashboard for my-strategy-bot.
Run with: streamlit run app.py
"""
import sys
import os
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from uuid import uuid4

from data.provider import fetch_daily_btc_usdt
from signals.ema_cross import compute_signals
from backtest.engine import BacktestEngine, INITIAL_CAPITAL
from backtest.trade_list import Trade
from validation.checks import (
    check_trade_count, check_plateau, regime_caveat, verdict
)
from config import Config

st.set_page_config(
    page_title="my-strategy-bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Sidebar ───────────────────────────────────────────────
st.sidebar.title("🤖 my-strategy-bot")
st.sidebar.markdown("EMA 9/21 Crossover · BTC/USDT Daily")

mode = st.sidebar.radio("Mode", ["Backtest", "Live Signals", "About"], index=0)

days_back = st.sidebar.slider("Data window (days)", 365, 1095, 1095, step=30)

ema_fast = st.sidebar.number_input("Fast EMA", min_value=3, max_value=50, value=9)
ema_slow = st.sidebar.number_input("Slow EMA", min_value=10, max_value=100, value=21)

run_btn = st.sidebar.button("🔄 Run Backtest", type="primary", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.caption(f"Capital: ${INITIAL_CAPITAL:,.0f} · Comm: 0.1%/side")

# ─── Data Cache ────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data(days):
    df = fetch_daily_btc_usdt(days_back=days)
    return df

@st.cache_data(ttl=300)
def run_backtest(days, fast, slow):
    df = load_data(days)
    engine = BacktestEngine(df, ema_fast=fast, ema_slow=slow)
    stats = engine.run_and_report()
    return df, engine, stats

# ─── Backtest Tab ──────────────────────────────────────────
if mode == "Backtest":
    st.title("📊 Backtest Results")

    if run_btn or "backtest_ran" not in st.session_state:
        with st.spinner("Fetching data and running backtest..."):
            try:
                df, engine, stats = run_backtest(days_back, ema_fast, ema_slow)
                st.session_state["backtest_ran"] = True
                st.session_state["df"] = df
                st.session_state["engine"] = engine
                st.session_state["stats"] = stats
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

    if "stats" in st.session_state:
        stats = st.session_state["stats"]
        df = st.session_state["df"]
        engine = st.session_state["engine"]

        # ── KPI Cards ──
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Final Equity", f"${stats['final_equity']:,.0f}",
                      f"{((stats['final_equity']/INITIAL_CAPITAL)-1)*100:.1f}%")
        with col2:
            st.metric("Strategy CAGR", f"{stats['cagr']:.2f}%",
                      f"{stats['cagr'] - stats['bh_cagr']:+.2f}pp vs B&H")
        with col3:
            st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
        with col4:
            st.metric("Profit Factor", f"{stats['profit_factor']:.2f}")
        with col5:
            st.metric("Max Drawdown", f"{stats['max_dd']:.1f}%")

        # ── Price + Signals Chart ──
        st.subheader("📈 Price & EMA Cross Signals")
        df_signals = compute_signals(df, fast=ema_fast, slow=ema_slow)

        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.6, 0.2, 0.2],
        )

        # Candlestick
        fig.add_trace(go.Candlestick(
            x=df["timestamp"],
            open=df["open"], high=df["high"],
            low=df["low"], close=df["close"],
            name="BTC/USDT", showlegend=False,
        ), row=1, col=1)

        # EMAs
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df_signals["ema_fast"],
            line=dict(color="blue", width=1.5), name=f"EMA {ema_fast}",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df_signals["ema_slow"],
            line=dict(color="red", width=1.5), name=f"EMA {ema_slow}",
        ), row=1, col=1)

        # Position indicator
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df_signals["position"],
            line=dict(color="green", width=2), name="Position (1=Long)",
        ), row=2, col=1)

        # Entry/Exit markers
        entries = df[df_signals["entry_signal"]]
        exits = df[df_signals["exit_signal"]]
        fig.add_trace(go.Scatter(
            x=entries["timestamp"], y=entries["close"],
            mode="markers", marker=dict(color="lime", size=10, symbol="triangle-up"),
            name="Entry Signal",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=exits["timestamp"], y=exits["close"],
            mode="markers", marker=dict(color="red", size=10, symbol="triangle-down"),
            name="Exit Signal",
        ), row=1, col=1)

        # Volume
        fig.add_trace(go.Bar(
            x=df["timestamp"], y=df["volume"],
            name="Volume", marker_color="gray", opacity=0.3,
        ), row=3, col=1)

        fig.update_layout(
            height=700,
            xaxis_rangeslider_visible=False,
            hovermode="x unified",
        )
        fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
        fig.update_yaxes(title_text="Position", row=2, col=1, range=[-0.1, 1.1])
        fig.update_yaxes(title_text="Volume", row=3, col=1)
        st.plotly_chart(fig, use_container_width=True, key="chart_main")

        # ── Trade List ──
        st.subheader("📋 Trade List")
        trades = stats["trades"]
        trade_data = []
        for t in trades:
            trade_data.append({
                "Entry": t.entry_date.strftime("%Y-%m-%d"),
                "Entry Price": f"${t.entry_price:,.2f}",
                "Exit": t.exit_date.strftime("%Y-%m-%d"),
                "Exit Price": f"${t.exit_price:,.2f}",
                "P&L %": f"{t.pnl_pct:+.2f}%",
                "Result": "✅ WIN" if t.win else "❌ LOSS",
                "Bars Held": t.bars_held,
            })
        st.dataframe(pd.DataFrame(trade_data), use_container_width=True, hide_index=True, key="trade_list")

        # ── Equity Curve ──
        st.subheader("💰 Equity Curve")
        equity_fig = go.Figure()
        equity_fig.add_trace(go.Scatter(
            x=df["timestamp"], y=stats["equity_curve"],
            line=dict(color="green", width=2),
            fill="tozeroy", fillcolor="rgba(0,200,0,0.1)",
            name="Portfolio Value",
        ))
        # Buy & Hold line
        bh_values = [INITIAL_CAPITAL * (c / df.iloc[0]["close"]) for c in df["close"]]
        equity_fig.add_trace(go.Scatter(
            x=df["timestamp"], y=bh_values,
            line=dict(color="gray", width=1.5, dash="dash"),
            name="Buy & Hold",
        ))
        equity_fig.update_layout(height=400, hovermode="x unified")
        equity_fig.update_yaxes(title_text="Portfolio Value ($)")
        st.plotly_chart(equity_fig, use_container_width=True, key="chart_equity")

        # ── Validation ──
        st.subheader("🔍 Validation Checks")
        col1, col2 = st.columns(2)
        with col1:
            st.info(check_trade_count(stats["total_trades"]))
            st.warning(regime_caveat())
        with col2:
            plateau_result = check_plateau(df, stats, (ema_fast, ema_slow))
            st.info(plateau_result)

        st.subheader("🏆 Verdict")
        v = verdict(stats, check_trade_count(stats["total_trades"]))
        if "WORTH TRADING" in v:
            st.success(v)
        elif "WORTH FIXING" in v:
            st.warning(v)
        else:
            st.error(v)

        # ── Verification Gate ──
        with st.expander("⚠️ Verification Gate — Cross-check with TradingView"):
            st.markdown("""
            **To verify this backtest against TradingView:**
            1. Open TradingView, symbol BTCUSDT, daily timeframe
            2. Apply indicators: EMA 9, EMA 21 on close
            3. Look at each crossover from oldest to newest
            4. Strategy rules:
               - Entry: when EMA 9 crosses ABOVE EMA 21, enter **next day at open**
               - Exit: when EMA 9 crosses BELOW EMA 21, exit **next day at open**
               - Commission: 0.1% per side (0.2% round trip)
               - Capital: 100% allocated per entry

            **⚠️ Discrepancy Risks:**
            - EMA calculation: TradingView uses SMA-based EMA initialization;
              this implementation uses pandas ewm(adjust=False). Minor discrepancies
              possible in first ~30 bars due to seed value differences.
            - Fill timing: This bot fills on NEXT bar open. In TradingView strategy
              tester, ensure you use 'open' for both entry and exit.
            - Focus verification on trades after bar 30+.
            """)

# ─── Live Signals Tab ──────────────────────────────────────
elif mode == "Live Signals":
    st.title("📡 Live Signal Monitor")

    auto_refresh = st.checkbox("Auto-refresh (30s)", value=True)

    placeholder = st.empty()

    refresh_counter = 0
    while True:
        refresh_counter += 1
        with placeholder.container():
            with st.spinner("Fetching latest data..."):
                try:
                    df = load_data(100)
                    df_signals = compute_signals(df, fast=ema_fast, slow=ema_slow)

                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    signal_row = df_signals.iloc[-2]
                    prev_signal = df_signals.iloc[-3] if len(df_signals) > 2 else None

                    current_price = latest["close"]
                    prev_close = prev["close"]
                    change = ((current_price - prev_close) / prev_close) * 100

                    # KPI row
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("BTC/USDT", f"${current_price:,.2f}", f"{change:+.2f}%")
                    with col2:
                        ema_fast_val = signal_row["ema_fast"]
                        ema_slow_val = signal_row["ema_slow"]
                        st.metric(f"EMA {ema_fast}", f"${ema_fast_val:,.2f}")
                    with col3:
                        st.metric(f"EMA {ema_slow}", f"${ema_slow_val:,.2f}")
                    with col4:
                        position = "🟢 LONG" if signal_row["position"] == 1 else "🔴 FLAT"
                        st.metric("Position", position)

                    # Signal alert
                    if signal_row["entry_signal"]:
                        st.success(f"🚦 **ENTRY SIGNAL** — EMA {ema_fast} crossed above EMA {ema_slow}!")
                    elif signal_row["exit_signal"]:
                        st.error(f"🚦 **EXIT SIGNAL** — EMA {ema_fast} crossed below EMA {ema_slow}!")
                    else:
                        st.info("⏸️ No cross signal — holding current position.")

                    # Mini chart
                    chart_key = f"live_chart_{refresh_counter}"
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df["timestamp"].iloc[-60:],
                        y=df["close"].iloc[-60:],
                        line=dict(color="orange", width=2),
                        name="Price",
                    ))
                    fig.add_trace(go.Scatter(
                        x=df["timestamp"].iloc[-60:],
                        y=df_signals["ema_fast"].iloc[-60:],
                        line=dict(color="blue", width=1.5),
                        name=f"EMA {ema_fast}",
                    ))
                    fig.add_trace(go.Scatter(
                        x=df["timestamp"].iloc[-60:],
                        y=df_signals["ema_slow"].iloc[-60:],
                        line=dict(color="red", width=1.5),
                        name=f"EMA {ema_slow}",
                    ))
                    fig.update_layout(height=400, hovermode="x unified")
                    st.plotly_chart(fig, use_container_width=True, key=chart_key)

                    st.caption(f"Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

                except Exception as e:
                    st.error(f"Error fetching data: {e}")

        if not auto_refresh:
            break
        time.sleep(30)

# ─── About Tab ─────────────────────────────────────────────
elif mode == "About":
    st.title("ℹ️ About my-strategy-bot")
    st.markdown("""
    ### Strategy
    - **Asset**: BTC/USDT · Daily candles only
    - **Entry**: Fast EMA crosses **above** Slow EMA → long, 100% capital
    - **Exit**: Fast EMA crosses **below** Slow EMA → flat
    - **Long-only**, no leverage
    - **Commission**: 0.1% per side
    - **Fill**: Next bar open
    - **Starting Capital**: $100,000

    ### Architecture
    | Module | Purpose |
    |--------|---------|
    | `data/` | Bybit public API OHLCV fetcher |
    | `signals/` | EMA crossover detection |
    | `backtest/` | Replay engine, trade list, stats |
    | `validation/` | Trade count, plateau check, regime caveat, verdict |
    | `execution/` | Paper, testnet, live exchange interfaces |
    | `state/` | SQLite position tracking |
    | `alerts/` | Telegram notifications |
    | `safety/` | API key validation, scam detection |

    ### Modes
    - `--backfill` — Backtest + validation + verification gate
    - `--paper` — Paper trading with simulated fills
    - `--testnet` — Bybit testnet (requires API keys)
    - `--live` — Live trading (safety gates enforced)

    ### Safety Rails
    - MAX_CAPITAL config — never reads live balance
    - Scam pattern detection in config
    - One position max (SQLite prevents double-entry)
    - No blind retries — errors → Telegram alert + halt
    - Live mode refuses start unless MAX_CAPITAL > 0
    """)

    st.code("streamlit run app.py", language="bash")