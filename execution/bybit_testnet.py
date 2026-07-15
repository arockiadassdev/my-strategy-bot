"""
Bybit testnet exchange.
Real API calls to testnet.bybit.com — no real funds.
"""
from typing import Dict
import time
import hashlib
import hmac
import requests
from .base import ExchangeBase
from config import Config


BYBIT_TESTNET_URL = "https://api-testnet.bybit.com"


def _sign_request(api_secret: str, params: dict) -> str:
    """Generate HMAC SHA256 signature for Bybit API v5."""
    param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hmac.new(
        api_secret.encode("utf-8"),
        param_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


class BybitTestnetExchange(ExchangeBase):
    """
    Bybit testnet exchange. Requires BYBIT_API_KEY and BYBIT_API_SECRET.
    One position max. Never retries blind on error — logs, alerts, halts.
    """

    def __init__(self):
        self.api_key = Config.BYBIT_API_KEY
        self.api_secret = Config.BYBIT_API_SECRET
        self.base_url = BYBIT_TESTNET_URL

    def _request(self, method: str, endpoint: str, params: dict = None) -> Dict:
        """Make a signed request to Bybit testnet."""
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
                raise RuntimeError(f"Bybit API error: {data.get('retMsg', 'unknown')}")
            return data
        except Exception as e:
            raise RuntimeError(f"Bybit testnet request failed: {e}")

    def get_current_price(self, instrument: str = "BTCUSDT") -> float:
        """Get current price from ticker endpoint."""
        data = self._request("GET", "/v5/market/tickers", {
            "category": "spot",
            "symbol": instrument,
        })
        ticker = data["result"]["list"][0]
        return float(ticker["lastPrice"])

    def place_buy_market(self, instrument: str, quantity: float) -> Dict:
        """Place a market buy order on testnet."""
        data = self._request("POST", "/v5/order/create", {
            "category": "spot",
            "symbol": instrument,
            "side": "Buy",
            "orderType": "Market",
            "qty": str(quantity),
            "timeInForce": "IOC",
        })
        return {
            "instrument": instrument,
            "side": "buy",
            "order_id": data["result"]["orderId"],
            "status": data["result"].get("orderStatus", "unknown"),
        }

    def place_sell_market(self, instrument: str, quantity: float) -> Dict:
        """Place a market sell order on testnet."""
        data = self._request("POST", "/v5/order/create", {
            "category": "spot",
            "symbol": instrument,
            "side": "Sell",
            "orderType": "Market",
            "qty": str(quantity),
            "timeInForce": "IOC",
        })
        return {
            "instrument": instrument,
            "side": "sell",
            "order_id": data["result"]["orderId"],
            "status": data["result"].get("orderStatus", "unknown"),
        }

    def get_account_info(self) -> Dict:
        """Get wallet balance (for safety checks only)."""
        data = self._request("GET", "/v5/account/wallet-balance", {
            "accountType": "UNIFIED",
            "coin": "USDT",
        })
        return data["result"]