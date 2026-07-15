"""
Bybit public API — daily BTC/USDT OHLCV fetcher.
No API key needed for public endpoints.

Falls back to a synthetic/demo dataset if Bybit returns 403/429 or network error.
"""
import time
import random
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

BYBIT_KLINE_URL = "https://api.bybit.com/v5/market/kline"
BACKUP_URL = "https://api.bybit.com/v5/market/kline"


def _generate_demo_data(days_back: int = 1095) -> pd.DataFrame:
    """
    Generate realistic demo BTC/USDT daily candles when live API is unavailable.
    Returns DataFrame with columns: timestamp, open, high, low, close, volume.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days_back)
    dates = list(pd.date_range(start=start, end=now, freq="D", tz=timezone.utc))

    # Seed-like random walk approximating BTC behavior
    base_price = 30000.0
    returns = np.random.normal(loc=0.001, scale=0.035, size=len(dates))  # ~1% daily drift, ~3.5% vol
    closes = base_price * np.exp(np.cumsum(returns))

    rows = []
    for i, ts in enumerate(dates):
        if i == 0:
            open_p = closes[i]
            close_p = closes[i]
            high_p = closes[i] * 1.02
            low_p = closes[i] * 0.98
            vol = random.uniform(20000, 50000)
        else:
            open_p = closes[i - 1]
            close_p = closes[i]
            change = close_p / open_p
            high_p = max(open_p, close_p) * random.uniform(1.0, 1.03)
            low_p = min(open_p, close_p) * random.uniform(0.97, 1.0)
            vol = random.uniform(20000, 50000) * (1 + abs(change - 1) * 10)

        rows.append({
            "timestamp": ts,
            "open": float(open_p),
            "high": float(high_p),
            "low": float(low_p),
            "close": float(float(close_p)),
            "volume": float(vol),
        })

    df = pd.DataFrame(rows)
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def fetch_daily_btc_usdt(days_back: int = 1095) -> pd.DataFrame:
    """
    Fetch daily BTC/USDT candles from Bybit.
    Default: ~3 years (1095 days).
    Returns DataFrame with columns: timestamp, open, high, low, close, volume.
    All prices as float. Timestamp as datetime (UTC).

    Falls back to demo data if API returns 403/429 or network error.
    """
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - days_back * 24 * 60 * 60 * 1000

    all_rows = []
    limit = 200  # max per request

    # First request: get the most recent 200 candles
    params = {
        "category": "spot",
        "symbol": "BTCUSDT",
        "interval": "D",
        "limit": limit,
    }
    try:
        resp = requests.get(BYBIT_KLINE_URL, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"⚠️ Bybit API returned HTTP {resp.status_code}, using demo data")
            return _generate_demo_data(days_back)
        data = resp.json()
        rc = data.get("retCode")
        if rc is None:
            print("⚠️ Bybit API returned non-JSON response, using demo data")
            return _generate_demo_data(days_back)
        if rc != 0:
            msg = data.get("retMsg", "unknown")
            if rc in (10001, 10002, 10003, 10020, 10021, 10022, 10023, 10024):
                print(f"⚠️ Bybit API error code {rc}: {msg}, using demo data")
                return _generate_demo_data(days_back)
            raise RuntimeError(f"Bybit API error: {msg}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Bybit API request failed: {e}, using demo data")
        return _generate_demo_data(days_back)

    result = data.get("result", {})
    candles = result.get("list", [])
    if not candles:
        print("⚠️ Bybit API returned no candles, using demo data")
        return _generate_demo_data(days_back)

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
        try:
            resp = requests.get(BYBIT_KLINE_URL, params=params, timeout=15)
            if resp.status_code != 200:
                print(f"⚠️ Bybit API pagination error {resp.status_code}, stopping")
                break
            data = resp.json()
            rc = data.get("retCode")
            if rc != 0:
                msg = data.get("retMsg", "unknown")
                if rc in (10001, 10002, 10003, 10020, 10021, 10022, 10023, 10024):
                    print(f"⚠️ Bybit pagination error code {rc}: {msg}, stopping")
                    break
                raise RuntimeError(f"Bybit API error: {msg}")
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Bybit pagination request failed: {e}, stopping")
            break

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
        print("⚠️ No data collected from Bybit API, using demo data")
        return _generate_demo_data(days_back)

    df = pd.DataFrame(all_rows)
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df
