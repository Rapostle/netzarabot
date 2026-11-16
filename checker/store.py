"""Small SQLite store: credits, payments and a per-day report cache. The owner never pays."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager


class Store:
    def __init__(self, path: str = "checker.db", owner_ids: tuple[int, ...] = ()):
        self.path = path
        self.owner_ids = set(int(i) for i in owner_ids)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (tg_id INTEGER PRIMARY KEY, credits INTEGER NOT NULL DEFAULT 0, created REAL);
                CREATE TABLE IF NOT EXISTS payments (txid TEXT PRIMARY KEY, tg_id INTEGER NOT NULL, usd REAL NOT NULL,
                    credits INTEGER NOT NULL, status TEXT NOT NULL, created REAL, approved REAL);
                CREATE TABLE IF NOT EXISTS reports (day TEXT, market TEXT, rule TEXT, payload TEXT, PRIMARY KEY (day, market, rule));
            """)

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def is_owner(self, tg_id: int) -> bool:
        return int(tg_id) in self.owner_ids

    def balance(self, tg_id: int) -> int:
        with self._db() as db:
            row = db.execute("SELECT credits FROM users WHERE tg_id=?", (int(tg_id),)).fetchone()
        return row[0] if row else 0

    def _ensure(self, db, tg_id: int) -> None:
        db.execute("INSERT OR IGNORE INTO users (tg_id, credits, created) VALUES (?, 0, ?)", (int(tg_id), time.time()))

    def spend_credit(self, tg_id: int) -> bool:
        """True when the check may run. Owners always may; others need a credit."""
        if self.is_owner(tg_id):
            return True
        with self._db() as db:
            self._ensure(db, tg_id)
            cur = db.execute("UPDATE users SET credits = credits - 1 WHERE tg_id=? AND credits > 0", (int(tg_id),))
            return cur.rowcount == 1

    def refund_credit(self, tg_id: int) -> None:
        if self.is_owner(tg_id):
            return
        with self._db() as db:
            self._ensure(db, tg_id)
            db.execute("UPDATE users SET credits = credits + 1 WHERE tg_id=?", (int(tg_id),))

    def submit_payment(self, txid: str, tg_id: int, usd: float, credits: int) -> bool:
        """Member says they paid. False if that transaction ID was already submitted by anyone."""
        txid = txid.strip().lower()
        with self._db() as db:
            self._ensure(db, tg_id)
            cur = db.execute("INSERT OR IGNORE INTO payments VALUES (?,?,?,?,?,?,NULL)",
                             (txid, int(tg_id), float(usd), int(credits), "pending", time.time()))
            return cur.rowcount == 1

    def approve_payment(self, txid: str) -> tuple[int, int] | None:
        """Credit the member once. Returns (tg_id, credits) or None if unknown or already approved."""
        txid = txid.strip().lower()
        with self._db() as db:
            row = db.execute("SELECT tg_id, credits, status FROM payments WHERE txid=?", (txid,)).fetchone()
            if not row or row[2] != "pending":
                return None
            db.execute("UPDATE payments SET status='approved', approved=? WHERE txid=?", (time.time(), txid))
            self._ensure(db, row[0])
            db.execute("UPDATE users SET credits = credits + ? WHERE tg_id=?", (row[1], row[0]))
            return row[0], row[1]

    def pending(self) -> list[tuple]:
        with self._db() as db:
            return db.execute("SELECT txid, tg_id, usd, credits FROM payments WHERE status='pending' ORDER BY created").fetchall()

    def cached_report(self, day: str, market: str, rule: str) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT payload FROM reports WHERE day=? AND market=? AND rule=?", (day, market, rule)).fetchone()
        return json.loads(row[0]) if row else None

    def save_report(self, day: str, market: str, rule: str, payload: dict) -> None:
        with self._db() as db:
            db.execute("INSERT OR REPLACE INTO reports VALUES (?,?,?,?)", (day, market, rule, json.dumps(payload)))

    def combinations_today(self, day: str) -> int:
        with self._db() as db:
            return db.execute("SELECT COUNT(*) FROM reports WHERE day=?", (day,)).fetchone()[0]
