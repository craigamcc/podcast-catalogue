"""SQLite store-of-record for the podcast catalogue metadata.

This is the durable, transactional backend for DataStore. It replaces the
JSONL-as-database pattern that made whole-file rewrites (and the ingest
data-loss bug) possible: every write here is a single transaction, so a crash
mid-write rolls back instead of truncating the catalogue.

Model: one row per normalized show (`title_key` = title.lower()), with the
full camelCase podcast dict stored as a JSON blob. Episodes live inside their
show's blob, mirroring the in-memory model where episodes are derived from
podcasts. LanceDB + Voyager remain the separate vector backend.
"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Dict, Iterator, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS podcasts (
    title_key TEXT PRIMARY KEY,
    title     TEXT NOT NULL,
    data      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class CatalogueDB:
    """Thin transactional wrapper around a single SQLite file.

    One connection per instance, used as a single writer. Reads and writes are
    wrapped in transactions; `replace_all` is atomic (all-or-nothing).
    """

    def __init__(self, path: str):
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # check_same_thread=False: the MCP server may touch the store from the
        # event loop's executor threads; we serialise writes ourselves and only
        # ever hold one connection, so this is safe here.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL improves concurrent-read/single-write behaviour and crash safety.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # --- writes -------------------------------------------------------------

    def upsert_show(self, title: str, data: Dict[str, Any]) -> None:
        """Insert or replace a single show. Transactional."""
        key = title.lower()
        with self._conn:  # implicit BEGIN/COMMIT, ROLLBACK on exception
            self._conn.execute(
                "INSERT INTO podcasts (title_key, title, data) VALUES (?, ?, ?) "
                "ON CONFLICT(title_key) DO UPDATE SET title=excluded.title, data=excluded.data",
                (key, title, json.dumps(data, ensure_ascii=False)),
            )

    def replace_all(self, shows: Dict[str, Dict[str, Any]]) -> None:
        """Atomically replace the entire catalogue.

        `shows` maps title_key -> normalized podcast dict. Runs in one
        transaction: on any error nothing is written (no partial/truncated
        state — the failure mode that made the JSONL rewrite dangerous).
        """
        rows = [
            (key, show.get("title", key), json.dumps(show, ensure_ascii=False))
            for key, show in shows.items()
        ]
        with self._conn:
            self._conn.execute("DELETE FROM podcasts")
            self._conn.executemany(
                "INSERT INTO podcasts (title_key, title, data) VALUES (?, ?, ?)", rows
            )

    def delete_show(self, title: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM podcasts WHERE title_key=?", (title.lower(),))

    def set_meta(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    # --- reads --------------------------------------------------------------

    def get_show(self, title: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT data FROM podcasts WHERE title_key=?", (title.lower(),)
        ).fetchone()
        return json.loads(row["data"]) if row else None

    def iter_shows(self) -> Iterator[Dict[str, Any]]:
        cur = self._conn.execute("SELECT data FROM podcasts ORDER BY title_key")
        for row in cur:
            yield json.loads(row["data"])

    def all_shows(self) -> List[Dict[str, Any]]:
        return list(self.iter_shows())

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) AS n FROM podcasts").fetchone()["n"]

    def get_meta(self, key: str) -> Optional[str]:
        row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def is_empty(self) -> bool:
        return self.count() == 0

    def close(self) -> None:
        self._conn.close()
