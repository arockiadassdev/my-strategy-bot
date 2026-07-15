"""
Backtest engine — replay daily bars, generate trades, compute equity curve.
Fill on next-bar open. Commission 0.1% per side.
"""
from typing import List, Tuple
import pandas as pd
from .trade_list import Trade, compute_pnl
from .stats import (
    compute_win_rate, compute_profit_factor,
    compute_max_drawdown, compute_cagr, print_trade_list
)
from signals.ema_cross import compute_signals

INITIAL_CAPITAL = 100_000.0
COMMISSION_PCT = 0.001


class BacktestEngine:
    def __init__(self, df: pd.DataFrame, ema_fast: int = 9, ema_slow: int = 21):
        """
        df: DataFrame from data provider (columns: timestamp, open, high, low, close, volume)
        Must be sorted oldest-first.
        """
        self.df = df.copy()
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow

    def run(self) -> Tuple[List[Trade], float, List[float]]:
        """
        Run the backtest.
        Returns: (trades, final_equity, equity_curve)
        """
        # Compute signals with configured EMA pair
        df = compute_signals(self.df, fast=self.ema_fast, slow=self.ema_slow)

        trades: List[Trade] = []
        equity_curve: List[float] = []
        in_position = False
        entry_price = 0.0
        entry_date = None
        entry_idx = -1
        capital = INITIAL_CAPITAL
        position_size = 0.0  # quantity of BTC held

        for i in range(len(df)):
            row = df.iloc[i]
            current_equity = capital

            if in_position:
                # Mark-to-market
                current_equity = capital + position_size * row["close"]

            # Check signals (signal generated on previous bar's close)
            # entry_signal at bar i means signal triggered at close of bar i
            # we fill at bar i+1 open
            # Similarly exit_signal at bar i means we fill at bar i+1 open

            if i > 0:
                prev_row = df.iloc[i - 1]

                # Enter on previous bar's entry_signal, fill at this bar's open
                if prev_row["entry_signal"] and not in_position:
                    fill_price = row["open"]
                    # 100% of capital, less commission
                    cost = capital * (1 - COMMISSION_PCT)
                    position_size = cost / fill_price
                    entry_price = fill_price
                    entry_date = row["timestamp"]
                    entry_idx = i
                    capital = 0.0
                    in_position = True

                # Exit on previous bar's exit_signal, fill at this bar's open
                elif prev_row["exit_signal"] and in_position:
                    fill_price = row["open"]
                    proceeds = position_size * fill_price * (1 - COMMISSION_PCT)
                    pnl = compute_pnl(entry_price, fill_price, COMMISSION_PCT)
                    trade = Trade(
                        entry_date=entry_date,
                        entry_price=entry_price,
                        exit_date=row["timestamp"],
                        exit_price=fill_price,
                        pnl_pct=pnl,
                        win=pnl > 0,
                        bars_held=i - entry_idx,
                    )
                    trades.append(trade)
                    capital = proceeds
                    position_size = 0.0
                    entry_price = 0.0
                    entry_date = None
                    in_position = False

            # Track equity
            if in_position:
                equity_curve.append(capital + position_size * row["close"])
            else:
                equity_curve.append(capital)

        # Close any open position at the last bar's close (for final equity)
        if in_position:
            last_row = df.iloc[-1]
            fill_price = last_row["close"]
            proceeds = position_size * fill_price * (1 - COMMISSION_PCT)
            pnl = compute_pnl(entry_price, fill_price, COMMISSION_PCT)
            trade = Trade(
                entry_date=entry_date,
                entry_price=entry_price,
                exit_date=last_row["timestamp"],
                exit_price=fill_price,
                pnl_pct=pnl,
                win=pnl > 0,
                bars_held=len(df) - entry_idx,
            )
            trades.append(trade)
            capital = proceeds
            equity_curve[-1] = capital
            in_position = False

        return trades, capital, equity_curve

    def run_and_report(self):
        """Run backtest and print full report with trade list and stats."""
        trades, final_equity, equity_curve = self.run()

        if not trades:
            print("\n⚠ No trades generated in the backtest period.")
            print(f"Final equity: ${final_equity:,.2f}")
            return

        # Summary stats
        total_trades = len(trades)
        win_rate = compute_win_rate(trades)
        profit_factor = compute_profit_factor(trades)
        max_dd = compute_max_drawdown(equity_curve)
        years = len(self.df) / 365.25
        cagr = compute_cagr(INITIAL_CAPITAL, final_equity, years)

        # Buy & hold return
        first_close = self.df.iloc[0]["close"]
        last_close = self.df.iloc[-1]["close"]
        bh_return = ((last_close - first_close) / first_close) * 100.0
        bh_cagr = compute_cagr(first_close, last_close, years)

        # Print trade list
        print_trade_list(trades)

        # Print summary
        print(f"\n{'='*60}")
        print("BACKTEST SUMMARY")
        print(f"{'='*60}")
        print(f"Period:          {self.df.iloc[0]['timestamp'].strftime('%Y-%m-%d')} → {self.df.iloc[-1]['timestamp'].strftime('%Y-%m-%d')} ({years:.1f} years)")
        print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
        print(f"Final Equity:    ${final_equity:,.2f}")
        print(f"Total Return:    {((final_equity / INITIAL_CAPITAL) - 1) * 100:.2f}%")
        print(f"Strategy CAGR:   {cagr:.2f}%")
        print(f"Buy & Hold CAGR: {bh_cagr:.2f}%")
        print(f"Buy & Hold Return: {bh_return:.2f}%")
        print(f"Total Trades:    {total_trades}")
        print(f"Win Rate:        {win_rate:.2f}%")
        print(f"Profit Factor:   {profit_factor:.2f}")
        print(f"Max Drawdown:    {max_dd:.2f}%")
        print(f"EMA Pair:        {self.ema_fast}/{self.ema_slow}")

        return {
            "trades": trades,
            "final_equity": final_equity,
            "equity_curve": equity_curve,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_dd": max_dd,
            "cagr": cagr,
            "bh_cagr": bh_cagr,
            "years": years,
        }