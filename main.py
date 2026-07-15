"""
my-strategy-bot — CLI entrypoint.
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from data.provider import fetch_daily_btc_usdt
from backtest.engine import BacktestEngine, INITIAL_CAPITAL
from validation.checks import (
    check_trade_count,
    check_plateau,
    regime_caveat,
    verdict,
)
from safety.checks import check_api_key_permissions, max_capital_safety_check, reject_deposit_scam_pattern
from alerts.telegram import alert_error


def cmd_backfill():
    """--backfill: fetch data, run backtest, run validation, print report."""
    print(f"Fetching {Config.BACKTEST_DAYS} days of BTC/USDT daily data from Bybit...")
    df = fetch_daily_btc_usdt(days_back=Config.BACKTEST_DAYS)
    print(f"Got {len(df)} daily bars ({df.iloc[0]['timestamp'].strftime('%Y-%m-%d')} → {df.iloc[-1]['timestamp'].strftime('%Y-%m-%d')})")

    # Run base backtest
    print("\n" + "█" * 60)
    print("█   RUNNING BACKTEST: EMA 9/21")
    print("█" * 60)
    engine = BacktestEngine(df, ema_fast=9, ema_slow=21)
    base_stats = engine.run_and_report()

    if base_stats:
        # Validation checks
        print("\n" + "█" * 60)
        print("█   VALIDATION CHECKS")
        print("█" * 60)
        print(check_trade_count(base_stats["total_trades"]))
        print(check_plateau(df, base_stats, (9, 21)))
        print(regime_caveat())
        print(verdict(base_stats, check_trade_count(base_stats["total_trades"])))

    # Verification gate info
    print("\n" + "█" * 60)
    print("█   VERIFICATION GATE")
    print("█" * 60)
    print(
        "To verify this backtest against TradingView:\n"
        "1. Open TradingView, symbol BTCUSDT, daily timeframe\n"
        "2. Apply indicators: EMA 9, EMA 21 on close\n"
        "3. Look at each crossover from oldest to newest\n"
        "4. Strategy rules:\n"
        "   - Entry: when EMA 9 crosses ABOVE EMA 21, enter next day at open\n"
        "   - Exit: when EMA 9 crosses BELOW EMA 21, exit next day at open\n"
        "   - Commission: 0.1% per side (0.2% round trip)\n"
        "   - Capital: 100% allocated per entry\n"
        "⚠️  DISCREPANCY RISKS:\n"
        "   - EMA calculation: TradingView uses SMA-based EMA initialization;\n"
        "     this implementation uses pandas ewm(adjust=False) which matches\n"
        "     the standard EMA formula. Minor discrepancies possible in first\n"
        "     few bars (9-21 bars) due to seed value differences.\n"
        "   - Fill timing: This bot fills on NEXT bar open. In TradingView\n"
        "     strategy tester, ensure you use 'open' for both entry and exit.\n"
        "   - Check: first few trades may differ slightly — this is expected\n"
        "     due to EMA warm-up. Focus validation on trades after bar 30+."
    )


def cmd_paper():
    """--paper: start the paper trading loop."""
    # Safety check: reject scam deposit patterns in config
    for key, val in os.environ.items():
        if reject_deposit_scam_pattern(f"{key}={val}"):
            alert_error(f"⚠️ SECURITY ALERT: Config contains deposit/scam pattern in {key}")
            print(f"❌ Refusing to start — config contains potential scam pattern in {key}")
            sys.exit(1)

    from paper_loop import run_paper_loop
    run_paper_loop()


def cmd_testnet():
    """--testnet: run on Bybit testnet."""
    Config.validate_testnet()

    # Safety check
    for key, val in os.environ.items():
        if reject_deposit_scam_pattern(f"{key}={val}"):
            print(f"❌ Refusing to start — config contains potential scam pattern in {key}")
            sys.exit(1)

    print("🔬 TESTNET MODE")
    print("   Connecting to Bybit testnet...")

    from state.sqlite_state import StateManager
    from execution.bybit_testnet import BybitTestnetExchange
    from signals.ema_cross import compute_signals
    from data.provider import fetch_daily_btc_usdt
    from alerts.telegram import alert_signal, alert_heartbeat

    state = StateManager()
    exchange = BybitTestnetExchange()

    print("   Connected to Bybit testnet")
    print("   Checking signals every 60 seconds...")
    print("   Press Ctrl+C to stop.\n")

    try:
        import time
        from datetime import datetime, timezone

        while True:
            df = fetch_daily_btc_usdt(days_back=100)
            df_signals = compute_signals(df)
            signal_row = df_signals.iloc[-2] if len(df_signals) > 1 else df_signals.iloc[-1]
            current_price = exchange.get_current_price()
            in_position = state.has_open_position()

            if signal_row["entry_signal"] and not in_position:
                capital = Config.MAX_CAPITAL
                quantity = capital / current_price
                fill = exchange.place_buy_market("BTCUSDT", quantity)
                state.open_position("BTCUSDT", current_price, quantity)
                alert_signal(f"✅ LONG ENTRY (testnet) @ ${current_price:.2f}")

            elif signal_row["exit_signal"] and in_position:
                pos = state.get_open_position()
                fill = exchange.place_sell_market("BTCUSDT", pos["quantity"])
                state.close_position(current_price, 0)
                alert_signal(f"❌ LONG EXIT (testnet) @ ${current_price:.2f}")

            # Daily heartbeat
            today = datetime.now(timezone.utc).date()
            if today != getattr(cmd_testnet, "_last_hb", None):
                cmd_testnet._last_hb = today
                status = "IN POSITION" if state.has_open_position() else "FLAT"
                alert_heartbeat(f"🤖 Bot alive — Testnet mode\nStatus: {status}\nBTC: ${current_price:.2f}")

            time.sleep(60)

    except KeyboardInterrupt:
        print("\n🛑 Testnet loop stopped.")
    finally:
        state.close()


def cmd_live():
    """--live: run live with full safety gates."""
    Config.validate_live()

    # Safety checks
    check_api_key_permissions(Config.BYBIT_API_KEY)
    if not max_capital_safety_check():
        raise RuntimeError("❌ MAX_CAPITAL must be > 0 for live mode.")

    for key, val in os.environ.items():
        if reject_deposit_scam_pattern(f"{key}={val}"):
            alert_error(f"Config contains deposit/scam pattern in {key}")
            raise RuntimeError(f"Refusing to start — scam pattern in {key}")

    print("🚀 LIVE MODE — All safety checks passed")
    print(f"   MAX_CAPITAL: ${Config.MAX_CAPITAL:,.2f}")
    print("   Connecting to Bybit live...")

    from state.sqlite_state import StateManager
    from execution.bybit_live import BybitLiveExchange
    from signals.ema_cross import compute_signals
    from data.provider import fetch_daily_btc_usdt
    from alerts.telegram import alert_signal, alert_heartbeat

    state = StateManager()
    exchange = BybitLiveExchange()

    print("   Connected to Bybit live")
    print("   Checking signals every 60 seconds...")
    print("   Press Ctrl+C to stop.\n")

    try:
        import time
        from datetime import datetime, timezone

        while True:
            df = fetch_daily_btc_usdt(days_back=100)
            df_signals = compute_signals(df)
            signal_row = df_signals.iloc[-2] if len(df_signals) > 1 else df_signals.iloc[-1]
            current_price = exchange.get_current_price()
            in_position = state.has_open_position()

            if signal_row["entry_signal"] and not in_position:
                quantity = Config.MAX_CAPITAL / current_price
                fill = exchange.place_buy_market("BTCUSDT", quantity)
                state.open_position("BTCUSDT", fill["fill_price"], fill["filled_qty"])
                alert_signal(f"✅ LIVE LONG ENTRY @ ${fill['fill_price']:.2f} | Qty: {fill['filled_qty']:.6f}")

            elif signal_row["exit_signal"] and in_position:
                pos = state.get_open_position()
                fill = exchange.place_sell_market("BTCUSDT", pos["quantity"])
                state.close_position(fill["fill_price"], 0)
                alert_signal(f"❌ LIVE LONG EXIT @ ${fill['fill_price']:.2f}")

            # Daily heartbeat
            today = datetime.now(timezone.utc).date()
            if today != getattr(cmd_live, "_last_hb", None):
                cmd_live._last_hb = today
                status = "IN POSITION" if state.has_open_position() else "FLAT"
                alert_heartbeat(f"🤖 Bot alive — LIVE mode\nStatus: {status}\nBTC: ${current_price:.2f}")

            time.sleep(60)

    except KeyboardInterrupt:
        print("\n🛑 Live loop stopped by user.")
        alert_error("Bot stopped by user.")
    finally:
        state.close()


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py --backfill         Run backtest + validation")
        print("  python main.py --paper            Run paper trading loop")
        print("  python main.py --testnet          Run on Bybit testnet")
        print("  python main.py --live             Run live (requires safety checks)")
        sys.exit(1)

    command = sys.argv[1]

    if command == "--backfill":
        cmd_backfill()
    elif command == "--paper":
        cmd_paper()
    elif command == "--testnet":
        cmd_testnet()
    elif command == "--live":
        cmd_live()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()