"""
Paper trading loop.
Checks signals once per day on the daily close.
Fills on next day's open. Stateful via SQLite.
Alerts via Telegram on every signal + daily heartbeat.
"""
import time
import sys
from datetime import datetime, timezone

from config import Config
from data.provider import fetch_daily_btc_usdt
from signals.ema_cross import compute_signals
from state.sqlite_state import StateManager
from alerts.telegram import alert_signal, alert_heartbeat, alert_error
from execution.simulator import PaperExchange


def run_paper_loop():
    """Main paper trading loop. Runs once per day."""
    print("📄 PAPER MODE — Starting paper trading loop")
    print(f"   Capital: ${Config.MAX_CAPITAL:,.2f}" if Config.MAX_CAPITAL > 0 else "   Capital: $100,000 (default)")

    state = StateManager()
    exchange = PaperExchange()

    print("   State DB: " + state.db_path)
    print("   Checking signals every 60 seconds (daily candle data)...")
    print("   Press Ctrl+C to stop.\n")

    last_bar_date = None
    heartbeat_sent_today = False

    try:
        while True:
            # Fetch fresh daily data
            df = fetch_daily_btc_usdt(days_back=100)
            latest_date = df.iloc[-1]["timestamp"].date()
            prev_date = df.iloc[-2]["timestamp"].date() if len(df) > 1 else latest_date

            # We evaluate signals at the daily close of the most recent complete bar
            # prev_row = the last COMPLETE daily bar (yesterday or today if market closed)
            eval_bar = df.iloc[-2] if len(df) > 1 else df.iloc[-1]

            # Compute signals
            df_signals = compute_signals(df)
            signal_row = df_signals.iloc[-2] if len(df_signals) > 1 else df_signals.iloc[-1]
            prev_signal_row = df_signals.iloc[-3] if len(df_signals) > 2 else None

            should_enter = bool(signal_row["entry_signal"])
            should_exit = bool(signal_row["exit_signal"])
            in_position = state.has_open_position()
            current_price = exchange.get_current_price()

            # --- ENTRY LOGIC ---
            if should_enter and not in_position:
                capital = exchange.capital
                quantity = capital / current_price
                fill = exchange.place_buy_market("BTCUSDT", quantity * 0.99)  # 99% to leave room
                state.open_position("BTCUSDT", fill["fill_price"], fill["quantity"])
                msg = (
                    f"✅ LONG ENTRY BTCUSDT\n"
                    f"Fill: ${fill['fill_price']:.2f}\n"
                    f"Qty: {fill['quantity']:.6f}\n"
                    f"Date: {latest_date}"
                )
                print(msg)
                alert_signal(msg)

            # --- EXIT LOGIC ---
            elif should_exit and in_position:
                pos = state.get_open_position()
                fill = exchange.place_sell_market("BTCUSDT", pos["quantity"])
                pnl_pct = ((fill["fill_price"] - pos["entry_price"]) / pos["entry_price"]) * 100
                pnl_net = pnl_pct - (Config.COMMISSION_PCT * 2 * 100)  # rough net
                state.close_position(fill["fill_price"], pnl_net)
                msg = (
                    f"❌ LONG EXIT BTCUSDT\n"
                    f"Fill: ${fill['fill_price']:.2f}\n"
                    f"P&L: {pnl_pct:.2f}% (net ~{pnl_net:.2f}%)\n"
                    f"Capital: ${fill['remaining_capital']:,.2f}\n"
                    f"Date: {latest_date}"
                )
                print(msg)
                alert_signal(msg)

            # --- STATUS REPORT ---
            in_position = state.has_open_position()
            if in_position:
                pos = state.get_open_position()
                unrealized = ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100
                status = (
                    f"IN POSITION since {pos['entry_time'][:10]} @ ${pos['entry_price']:.2f} | "
                    f"Current: ${current_price:.2f} | "
                    f"Unrealized: {unrealized:.2f}%"
                )
            else:
                status = f"FLAT | Capital: ${exchange.capital:,.2f}"

            # Send heartbeat once per day
            today = datetime.now(timezone.utc).date()
            if today != getattr(run_paper_loop, "_last_heartbeat_date", None):
                run_paper_loop._last_heartbeat_date = today
                alert_heartbeat(
                    f"🤖 Bot alive — Paper mode\n"
                    f"Date: {today}\n"
                    f"{status}\n"
                    f"No new signals today." if not (should_enter or should_exit) else f"Signal sent today."
                )
                print(f"💓 Heartbeat sent for {today}")
                print(f"📊 Status: {status}")

            # Wait before next check
            time.sleep(60)  # Check every 60 seconds (for demo; in prod use 1h+)

    except KeyboardInterrupt:
        print("\n🛑 Paper loop stopped by user.")
    except Exception as e:
        alert_error(f"Paper loop crashed: {e}")
        print(f"🚨 Fatal error: {e}")
        sys.exit(1)
    finally:
        state.close()