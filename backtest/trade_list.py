"""
Trade record dataclass and P&L calculation.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:
    entry_date: datetime
    entry_price: float
    exit_date: datetime
    exit_price: float
    pnl_pct: float       # net of commissions, expressed as %
    win: bool             # True if pnl_pct > 0
    bars_held: int


def compute_pnl(entry_price: float, exit_price: float, commission_pct: float = 0.001) -> float:
    """
    Compute net P&L % for a long trade.
    Commission applied on entry and exit (0.1% per side default).
    Formula: (exit_price * (1 - comm) - entry_price * (1 + comm)) / (entry_price * (1 + comm))
    """
    cost_basis = entry_price * (1 + commission_pct)
    proceeds = exit_price * (1 - commission_pct)
    return (proceeds - cost_basis) / cost_basis * 100.0