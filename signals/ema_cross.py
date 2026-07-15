"""
EMA crossover detection.
Evaluated ONCE per daily bar (at the close).
No intra-candle logic.
"""
import pandas as pd
import numpy as np


def compute_signals(df: pd.DataFrame, fast: int = 9, slow: int = 21) -> pd.DataFrame:
    """
    Given a DataFrame with 'close' column (sorted oldest-first),
    compute fast-period and slow-period EMAs.
    Returns the DataFrame with added columns:
        ema_fast, ema_slow, position (1 = long, 0 = flat),
        entry_signal, exit_signal
    signal is set on the bar where the cross occurs (at close).
    The actual fill happens on the NEXT bar's open.
    """
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=slow, adjust=False).mean()

    # 1 if ema_fast > ema_slow, else 0
    df["position"] = np.where(df["ema_fast"] > df["ema_slow"], 1, 0)

    # Detect changes: 0->1 means enter long, 1->0 means exit
    df["entry_signal"] = (df["position"] == 1) & (df["position"].shift(1) == 0)
    df["exit_signal"] = (df["position"] == 0) & (df["position"].shift(1) == 1)

    return df
