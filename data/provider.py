"""
Bybit public API — daily BTC/USDT OHLCV fetcher.
No API key needed for public endpoints.
"""
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"

def fetch_daily_btc_usdt(days_back: int = 1095) -> pd.DataFrame:
    """
    Fetch daily BTC/USDT candles from Bybit.
    Default: ~3 years (1095 days).
    Returns DataFrame with columns: timestamp, open, high, low, close, volume.
    All prices as float. Timestamp as datetime (UTC).

    Paginates backward using the 'end' parameter.
    Bybit returns newest-first per request.
    """
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - days_back * 24 * 60 * 60 * 1000

    all_rows = []
    limit = 200

    # First request: get the most recent 200 candles
    params = {
        "category": "spot",
        "symbol": "BTCUSDT",
        "interval": "D",
        "limit": limit,
    }
    resp = requests.get(BYBIT_KLINE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit API error: {data.get('retMsg', 'unknown')}")

    result = data.get("result", {})
    candles = result.get("list", [])
    if not candles:
        raise RuntimeError("No data returned from Bybit API.")

    for c in reversed(candles):
        ts = int(c[0])
        all_rows.append({
            "timestamp": datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]),
        })

    # Paginate backward using 'end' parameter
    while len(candles) == limit:
        oldest_ts = int(candles[-1][0])
        if oldest_ts <= start_ms:
            break
        next_end = oldest_ts - 1
        time.sleep(0.3)

        params = {
            "category": "spot",
            "symbol": "BTCUSDT",
            "interval": "D",
            "end": next_end,
            "limit": limit,
        }
        resp = requests.get(BYBIT_KLINE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode") != 0:
            raise RuntimeError(f"Bybit API error: {data.get('retMsg', 'unknown')}")

        result = data.get("result", {})
        candles = result.get("list", [])
        if not candles:
            break

        for c in reversed(candles):
            ts = int(c[0])
            if ts < start_ms:
                continue
            all_rows.append({
                "timestamp": datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })

    if not all_rows:
        raise RuntimeError("No data returned from Bybit API.")

    df = pd.DataFrame(all_rows)
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df
