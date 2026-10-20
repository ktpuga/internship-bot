"""SQLite record of which posting IDs we've already handled.

This is the bot's only state. If the container restarts, the DB (on a mounted
volume) is what stops it from re-posting everything.
"""
from __future__ import annotations

import os
import sqlite3
import time
from typing import Iterable


class SeenStore:
    def __init__(self, path: str):
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS seen ("
            " id TEXT PRIMARY KEY,"
            " seen_at INTEGER NOT NULL,"
            " posted INTEGER NOT NULL DEFAULT 0)"
        )
        # Small key/value table for bot state (e.g. the filter fingerprint).
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.commit()

    def get_meta(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
        self.db.commit()

    def is_empty(self, prefix: str = "") -> bool:
        """True if no seen IDs start with `prefix` (whole table if prefix is "")."""
        row = self.db.execute(
            "SELECT 1 FROM seen WHERE substr(id, 1, ?) = ? LIMIT 1",
            (len(prefix), prefix),
        ).fetchone()
        return row is None

    def migrate_unprefixed(self, prefix: str) -> int:
        """Move IDs saved before per-source namespacing (no ':') under `prefix`.

        Idempotent: once nothing un-prefixed is left this is a no-op. Also drops the
        old single-source fingerprint key, which nothing reads anymore.
        """
        n = self.db.execute("SELECT COUNT(*) FROM seen WHERE instr(id, ':') = 0").fetchone()[0]
        if n:
            self.db.execute(
                "INSERT OR IGNORE INTO seen (id, seen_at, posted) "
                "SELECT ? || id, seen_at, posted FROM seen WHERE instr(id, ':') = 0",
                (prefix,),
            )
            self.db.execute("DELETE FROM seen WHERE instr(id, ':') = 0")
        self.db.execute("DELETE FROM meta WHERE key = 'filter_fingerprint'")
        self.db.commit()
        return n

    def unseen(self, ids: Iterable[str]) -> set[str]:
        ids = list(ids)
        if not ids:
            return set()
        seen: set[str] = set()
        # Query in chunks to stay under SQLite's variable limit.
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            q = f"SELECT id FROM seen WHERE id IN ({','.join('?' * len(chunk))})"
            seen.update(r[0] for r in self.db.execute(q, chunk))
        return set(ids) - seen

    def mark(self, ids: Iterable[str], posted: bool = False) -> None:
        now = int(time.time())
        self.db.executemany(
            "INSERT OR IGNORE INTO seen (id, seen_at, posted) VALUES (?, ?, ?)",
            [(i, now, int(posted)) for i in ids],
        )
        self.db.commit()

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM seen").fetchone()[0]

    def close(self) -> None:
        self.db.close()
