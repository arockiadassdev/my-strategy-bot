"""
Validation checks run automatically after backfill.
"""
from typing import Optional, Dict
from backtest.trade_list import Trade
from backtest.engine import BacktestEngine
import pandas as pd


def check_trade_count(trades_count: int) -> str:
    """Flag if under 20 trades."""
    if trades_count == 0:
        return "❌ CRITICAL: Zero trades generated. Strategy produced no signals in this period."
    elif trades_count < 10:
        return f"⚠️ ALERT: Only {trades_count} trades — anecdote, not evidence. Not statistically meaningful."
    elif trades_count < 20:
        return f"⚠️ WARNING: Only {trades_count} trades. Below 20-trade threshold — anecdote, not evidence."
    else:
        return f"✅ Trade count: {trades_count} — sufficient for statistical relevance."


def check_plateau(df: pd.DataFrame, base_stats: Dict, base_ema: tuple) -> str:
    """
    Re-run backtest on neighboring EMA pairs (8/20, 10/22).
    If performance holds → plateau = real edge.
    If collapses → spike = curve-fit.
    """
    lines = ["\n--- PLATEAU / OVERFITTING CHECK ---"]

    neighbors = [(8, 20), (10, 22)]
    base_cagr = base_stats.get("cagr", 0)

    results = {}
    for fast, slow in neighbors:
        engine = BacktestEngine(df, ema_fast=fast, ema_slow=slow)
        trades, final_equity, equity_curve = engine.run()
        if trades:
            total_trades = len(trades)
            win_rate = sum(1 for t in trades if t.win) / total_trades * 100
            total_return = ((final_equity / 100_000.0) - 1) * 100
            results[(fast, slow)] = {
                "total_trades": total_trades,
                "win_rate": win_rate,
                "total_return": total_return,
                "final_equity": final_equity,
            }

    # Compare
    cagr_variations: list[float] = [base_cagr]
    for ema_pair, r in results.items():
        # Rough CAGR approximation from total return
        years = len(df) / 365.25
        if years > 0:
            cagr_r = ((r["final_equity"] / 100_000.0) ** (1 / years) - 1) * 100
        else:
            cagr_r = 0
        cagr_variations.append(cagr_r)
        diff = cagr_r - base_cagr
        lines.append(
            f"  EMA {ema_pair[0]}/{ema_pair[1]}: {r['total_trades']} trades, "
            f"return {r['total_return']:.2f}%, CAGR ≈ {cagr_r:.2f}% "
            f"({'+' if diff >= 0 else ''}{diff:.2f}pp vs base)"
        )

    max_variation = max(cagr_variations) - min(cagr_variations)
    if max_variation < 5:
        lines.append(
            f"\n✅ VERDICT: CAQR varies by only {max_variation:.2f}pp across neighboring EMA pairs."
            "\n   → This is a PLATEAU. The signal is robust and not curve-fit."
        )
    elif max_variation < 20:
        lines.append(
            f"\n⚠️ VERDICT: CAGR varies by {max_variation:.2f}pp across neighboring EMA pairs."
            "\n   → Moderate sensitivity. The edge exists but is fragile."
        )
    else:
        lines.append(
            f"\n❌ VERDICT: CAGR varies by {max_variation:.2f}pp across neighboring EMA pairs."
            "\n   → This is a SPIKE. The base parameters are likely curve-fit."
        )

    return "\n".join(lines)


def regime_caveat() -> str:
    """Print the regime caveat about BTC trend characteristics."""
    return (
        "\n--- REGIME CAVEAT ---\n"
        "BTC/USDT has historically averaged ~1.7% daily volatility with strong trending "
        "behavior. This EMA crossover strategy is specifically tuned for such violent trends.\n"
        "⚠️ Do NOT assume portability to:\n"
        "   - Other assets (equities, forex, commodities)\n"
        "   - Lower timeframes (hourly, minute)\n"
        "   - Range-bound / grinding markets\n"
        "A fresh backtest is required for any change in asset or timeframe."
    )


def verdict(base_stats: Dict, trade_count_check: str) -> str:
    """
    Honest verdict: worth trading, worth fixing, or worth binning.
    """
    cagr = base_stats.get("cagr", 0)
    bh_cagr = base_stats.get("bh_cagr", 0)
    pf = base_stats.get("profit_factor", 0)
    max_dd = base_stats.get("max_dd", 0)
    total_trades = base_stats.get("total_trades", 0)

    lines = ["\n" + "=" * 60, "HONEST VERDICT", "=" * 60]

    # Build reasoning
    reasons = []

    if total_trades < 20:
        reasons.append(f"❌ Only {total_trades} trades — not statistically meaningful.")
    elif total_trades < 50:
        reasons.append(f"⚠️ {total_trades} trades — barely adequate sample size.")

    if cagr > bh_cagr and cagr > 0:
        reasons.append(f"✅ Strategy CAGR ({cagr:.2f}%) beats Buy & Hold ({bh_cagr:.2f}%).")
    elif cagr > 0:
        reasons.append(f"⚠️ Strategy CAGR ({cagr:.2f}%) underperforms Buy & Hold ({bh_cagr:.2f}%).")
    else:
        reasons.append(f"❌ Strategy CAGR is negative ({cagr:.2f}%).")

    if pf >= 2.0:
        reasons.append(f"✅ Profit factor {pf:.2f} — excellent risk/reward.")
    elif pf >= 1.5:
        reasons.append(f"✅ Profit factor {pf:.2f} — solid.")
    elif pf >= 1.0:
        reasons.append(f"⚠️ Profit factor {pf:.2f} — barely profitable.")
    else:
        reasons.append(f"❌ Profit factor {pf:.2f} — unprofitable.")

    if max_dd > 50:
        reasons.append(f"❌ Max drawdown {max_dd:.2f}% — extreme, likely exceeds risk tolerance.")
    elif max_dd > 30:
        reasons.append(f"⚠️ Max drawdown {max_dd:.2f}% — high but possibly survivable.")
    else:
        reasons.append(f"✅ Max drawdown {max_dd:.2f}% — reasonable.")

    lines.extend(reasons)
    lines.append("")

    # Final verdict
    positives = sum(1 for r in reasons if r.startswith("✅"))
    warnings = sum(1 for r in reasons if r.startswith("⚠️"))
    negatives = sum(1 for r in reasons if r.startswith("❌"))

    if positives >= 3 and negatives == 0:
        lines.append("🥇 VERDICT: WORTH TRADING — This strategy shows a genuine, robust edge on BTC/USDT daily.")
    elif positives >= 2 and warnings <= 2:
        lines.append("🔧 VERDICT: WORTH FIXING — The core edge exists but needs refinement (e.g., stop losses, partial exits).")
    else:
        lines.append("🗑️ VERDICT: WORTH BINNING — Insufficient edge to justify live trading on current data.")

    return "\n".join(lines)