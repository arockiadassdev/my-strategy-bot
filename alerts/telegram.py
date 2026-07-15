"""
Telegram alert sender.
Sends messages on every signal + daily heartbeat.
"""
from typing import Optional
import requests
from config import Config


def send_telegram(message: str) -> bool:
    """Send a Telegram message. Returns True if sent, False if not configured."""
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": Config.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"⚠️ Telegram send failed: {e}")
        return False


def alert_signal(message: str):
    """Send a signal alert (entry/exit)."""
    sent = send_telegram(f"🚦 <b>SIGNAL</b>\n{message}")
    if sent:
        print(f"📨 Telegram alert sent: {message[:60]}...")


def alert_heartbeat(message: str):
    """Send a daily heartbeat (even on no-signal days)."""
    sent = send_telegram(f"💓 <b>Heartbeat</b>\n{message}")
    if sent:
        print(f"📨 Heartbeat sent")


def alert_error(message: str):
    """Send an error alert and halt."""
    send_telegram(f"🚨 <b>ERROR — BOT HALTED</b>\n{message}")
    print(f"🚨 ERROR: {message}")