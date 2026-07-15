"""
Paper trading simulator.
Fills at next-bar open from data provider. No real orders.
"""
from typing import Dict
from .base import ExchangeBase
from config import Config
from data.provider import fetch_daily_btc_usdt
import pandas as pd


class PaperExchange(ExchangeBase):
    """
    Simulated exchange for paper mode.
    Fills are determined by the next available daily open price.
    Uses MAX_CAPITAL from config for position sizing.
    """

    def __init__(self):
        self._price_cache: pd.DataFrame = fetch_daily_btc_usdt(days_back=5)
        self._capital = Config.MAX_CAPITAL if Config.MAX_CAPITAL > 0 else 100_000.0

    def get_current_price(self, instrument: str = "BTCUSDT") -> float:
        """Return the most recent daily close as the 'current price'."""
        return float(self._price_cache.iloc[-1]["close"])

    def get_today_open(self) -> float:
        """Return today's open (for fill simulation)."""
        return float(self._price_cache.iloc[-1]["open"])

    def place_buy_market(self, instrument: str, quantity: float) -> Dict:
        """Simulate a market buy — fill at today's open."""
        fill_price = self.get_today_open()
        cost = fill_price * quantity * (1 + Config.COMMISSION_PCT)
        self._capital -= cost
        return {
            "instrument": instrument,
            "side": "buy",
            "fill_price": fill_price,
            "quantity": quantity,
            "cost": cost,
            "remaining_capital": self._capital,
            "status": "filled",
        }

    def place_sell_market(self, instrument: str, quantity: float) -> Dict:
        """Simulate a market sell — fill at today's open."""
        fill_price = self.get_today_open()
        proceeds = fill_price * quantity * (1 - Config.COMMISSION_PCT)
        self._capital += proceeds
        return {
            "instrument": instrument,
            "side": "sell",
            "fill_price": fill_price,
            "quantity": quantity,
            "proceeds": proceeds,
            "remaining_capital": self._capital,
            "status": "filled",
        }

    def get_account_info(self) -> Dict:
        return {"capital": self._capital, "mode": "paper"}

    @property
    def capital(self) -> float:
        return self._capital