"""
Configuration loader.
Reads from environment variables or .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Mode: paper, testnet, live
    MODE: str = os.getenv("MODE", "paper").lower()

    # Exchange API
    BYBIT_API_KEY: str = os.getenv("BYBIT_API_KEY", "")
    BYBIT_API_SECRET: str = os.getenv("BYBIT_API_SECRET", "")

    # Capital (required for live mode)
    MAX_CAPITAL: float = float(os.getenv("MAX_CAPITAL", "0"))

    # Telegram alerts
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Backtest defaults
    BACKTEST_DAYS: int = int(os.getenv("BACKTEST_DAYS", "1095"))
    INITIAL_CAPITAL: float = 100_000.0
    COMMISSION_PCT: float = 0.001

    @classmethod
    def validate_live(cls) -> None:
        """Validate that live mode can start safely."""
        errors = []
        if not cls.BYBIT_API_KEY:
            errors.append("BYBIT_API_KEY is required for live mode.")
        if not cls.BYBIT_API_SECRET:
            errors.append("BYBIT_API_SECRET is required for live mode.")
        if cls.MAX_CAPITAL <= 0:
            errors.append("MAX_CAPITAL must be set to a positive value for live mode.")
        if errors:
            raise RuntimeError(
                "Live mode safety check failed:\n" + "\n".join(errors)
            )

    @classmethod
    def validate_testnet(cls) -> None:
        """Validate testnet has keys."""
        if not cls.BYBIT_API_KEY or not cls.BYBIT_API_SECRET:
            raise RuntimeError("BYBIT_API_KEY and BYBIT_API_SECRET required for testnet mode.")