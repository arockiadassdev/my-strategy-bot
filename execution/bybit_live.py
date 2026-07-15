"""
Bybit live exchange. Refuses to start unless safety checks pass.
Never uses account balance for sizing — only MAX_CAPITAL config.
Never retries blind on error — logs, alerts via Telegram, halts.
"""
from typing import Dict
import time
import hashlib
import hmac
import requests
from .base import ExchangeBase
from config import Config
from alerts.telegram import alert_error


BYBIT_LIVE_URL = "https://api.bybit.com"


def _sign_request(api_secret: str, params: dict) -> str:
    param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hmac.new(
        api_secret.encode("utf-8"),
        param_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


class BybitLiveExchange(ExchangeBase):
    """
    Bybit live exchange. One position max.
    Safety gates:
      - MAX_CAPITAL > 0 (never reads live balance for sizing)
      - API key must be set
      - Any error → alert via Telegram + halt
    """

    def __init__(self):
        # Safety gate: validate before init
        Config.validate_live()
        self.api_key = Config.BYBIT_API_KEY
        self.api_secret = Config.BYBIT_API_SECRET
        self.base_url = BYBIT_LIVE_URL
        self.max_capital = Config.MAX_CAPITAL

    def _request(self, method: str, endpoint: str, params: dict = None) -> Dict:
        timestamp = str(int(time.time() * 1000))
        if params is None:
            params = {}
        params["api_key"] = self.api_key
        params["timestamp"] = timestamp
        params["sign"] = _sign_request(self.api_secret, params)

        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                resp = requests.get(url, params=params, timeout=15)
            else:
                resp = requests.post(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("retCode") != 0:
                msg = f"Bybit API error: {data.get('retMsg', 'unknown')}"
                alert_error(msg)
                raise RuntimeError(msg)
            return data
        except requests.exceptions.Timeout:
            msg = "Bybit API request timed out — halting"
            alert_error(msg)
            raise RuntimeError(msg)
        except requests.exceptions.ConnectionError:
            msg = "Bybit API connection failed — halting"
            alert_error(msg)
            raise RuntimeError(msg)
        except Exception as e:
            msg = f"Bybit live request failed: {e}"
            alert_error(msg)
            raise RuntimeError(msg)

    def get_current_price(self, instrument: str = "BTCUSDT") -> float:
        try:
            data = self._request("GET", "/v5/market/tickers", {
                "category": "spot",
                "symbol": instrument,
            })
            ticker = data["result"]["list"][0]
            return float(ticker["lastPrice"])
        except Exception as e:
            alert_error(f"Failed to get price: {e}")
            raise

    def place_buy_market(self, instrument: str, quantity: float) -> Dict:
        try:
            data = self._request("POST", "/v5/order/create", {
                "category": "spot",
                "symbol": instrument,
                "side": "Buy",
                "orderType": "Market",
                "qty": str(quantity),
                "timeInForce": "IOC",
            })
            result = data["result"]
            order_status = result.get("orderStatus", "unknown")
            if order_status in ("Rejected", "Cancelled"):
                alert_error(f"Buy order rejected: {result}")
                raise RuntimeError(f"Buy order rejected: {result}")
            return {
                "instrument": instrument,
                "side": "buy",
                "order_id": result["orderId"],
                "fill_price": float(result.get("avgPrice", 0)),
                "filled_qty": float(result.get("cumExecQty", 0)),
                "status": order_status,
            }
        except Exception as e:
            alert_error(f"Buy order failed: {e}")
            raise

    def place_sell_market(self, instrument: str, quantity: float) -> Dict:
        try:
            data = self._request("POST", "/v5/order/create", {
                "category": "spot",
                "symbol": instrument,
                "side": "Sell",
                "orderType": "Market",
                "qty": str(quantity),
                "timeInForce": "IOC",
            })
            result = data["result"]
            order_status = result.get("orderStatus", "unknown")
            if order_status in ("Rejected", "Cancelled"):
                alert_error(f"Sell order rejected: {result}")
                raise RuntimeError(f"Sell order rejected: {result}")
            return {
                "instrument": instrument,
                "side": "sell",
                "order_id": result["orderId"],
                "fill_price": float(result.get("avgPrice", 0)),
                "filled_qty": float(result.get("cumExecQty", 0)),
                "status": order_status,
            }
        except Exception as e:
            alert_error(f"Sell order failed: {e}")
            raise

    def get_account_info(self) -> Dict:
        """For safety checks only — never used for sizing."""
        try:
            data = self._request("GET", "/v5/account/wallet-balance", {
                "accountType": "UNIFIED",
                "coin": "USDT",
            })
            return data["result"]
        except Exception as e:
            alert_error(f"Failed to get account info: {e}")
            raise