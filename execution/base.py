"""
Abstract exchange interface.
All execution modules must implement this.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict


class ExchangeBase(ABC):
    @abstractmethod
    def get_current_price(self, instrument: str = "BTCUSDT") -> float:
        """Get the current market price."""
        ...

    @abstractmethod
    def place_buy_market(self, instrument: str, quantity: float) -> Dict:
        """Place a market buy order. Returns fill info dict."""
        ...

    @abstractmethod
    def place_sell_market(self, instrument: str, quantity: float) -> Dict:
        """Place a market sell order. Returns fill info dict."""
        ...

    @abstractmethod
    def get_account_info(self) -> Dict:
        """Get account info (for safety checks — never used for sizing)."""
        ...