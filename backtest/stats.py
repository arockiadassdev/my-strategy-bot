"""
Summary statistics for backtest results.
"""
from typing import List
import numpy as np
from .trade_list import Trade


def compute_win_rate(trades: List[Trade]) -> float:
    if not trades:
        return 0.0
    return sum(1 for t in trades if t.win) / len(trades) * 100.0


def compute_profit_factor(trades: List[Trade]) -> float:
    gross_win = sum(t.pnl_pct for t in trades if t.win)
    gross_loss = abs(sum(t.pnl_pct for t in trades if not t.win))
    if gross_loss == 0:
        return float("inf")
    return gross_win / gross_loss


def compute_max_drawdown(equity_curve: List[float]) -> float:
    """
    Max drawdown as percentage from peak.
    equity_curve: list of portfolio values over time.
    """
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def compute_cagr(start_value: float, end_value: float, years: float) -> float:
    if years <= 0 or start_value <= 0:
        return 0.0
    return ((end_value / start_value) ** (1 / years) - 1) * 100.0


def print_trade_list(trades: List[Trade]):
    """Print formatted trade list."""
    print("\n" + "=" * 120)
    print(f"{'Entry Date':<20} {'Entry Price':<14} {'Exit Date':<20} {'Exit Price':<14} {'P&L %':<10} {'Result':<8} {'Bars':<6}")
    print("=" * 120)
    for t in trades:
        result = "WIN" if t.win else "LOSS"
        print(f"{t.entry_date.strftime('%Y-%m-%d'):<20} {t.entry_price:<14.2f} "
              f"{t.exit_date.strftime('%Y-%m-%d'):<20} {t.exit_price:<14.2f} "
              f"{t.pnl_pct:<10.2f} {result:<8} {t.bars_held:<6}")
    print("=" * 120)