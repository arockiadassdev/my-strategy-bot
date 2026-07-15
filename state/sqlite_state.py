"""
SQLite state manager for position tracking.
Ensures restarts never double-enter a position.
"""
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, Dict


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot_state.db")


class StateManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                entry_time TEXT NOT NULL,
                quantity REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                exit_price REAL,
                exit_time TEXT,
                pnl_pct REAL
            )
        """)
        self.conn.commit()

    def get_open_position(self, instrument: str = "BTCUSDT") -> Optional[Dict]:
        """Return the open position dict if one exists, else None."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM position WHERE instrument = ? AND status = 'open' ORDER BY id DESC LIMIT 1",
            (instrument,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "instrument": row[1],
            "side": row[2],
            "entry_price": row[3],
            "entry_time": row[4],
            "quantity": row[5],
            "status": row[6],
            "exit_price": row[7],
            "exit_time": row[8],
            "pnl_pct": row[9],
        }

    def has_open_position(self, instrument: str = "BTCUSDT") -> bool:
        return self.get_open_position(instrument) is not None

    def open_position(self, instrument: str, entry_price: float, quantity: float):
        """Record a new long position."""
        cursor = self.conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO position (instrument, side, entry_price, entry_time, quantity, status) VALUES (?, 'long', ?, ?, ?, 'open')",
            (instrument, entry_price, now, quantity)
        )
        self.conn.commit()

    def close_position(self, exit_price: float, pnl_pct: float):
        """Close the current open position."""
        pos = self.get_open_position()
        if pos is None:
            raise RuntimeError("No open position to close.")
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE position SET status = 'closed', exit_price = ?, exit_time = ?, pnl_pct = ? WHERE id = ?",
            (exit_price, now, pnl_pct, pos["id"])
        )
        self.conn.commit()

    def close(self):
        self.conn.close()