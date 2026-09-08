from __future__ import annotations

import json, sqlite3, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

COLLECTIONS = {"opportunities", "evidence", "packets", "blockers", "approvals", "jobs", "outcomes", "ledger", "reservations", "inbox", "audit"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str): self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        try: yield con
        finally: con.close()

    def init(self) -> None:
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS records(collection TEXT NOT NULL,id TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(collection,id));
            CREATE INDEX IF NOT EXISTS records_collection ON records(collection,created_at);
            CREATE TABLE IF NOT EXISTS policy(singleton INTEGER PRIMARY KEY CHECK(singleton=1),cash_buffer_cents INTEGER NOT NULL,daily_limit_cents INTEGER NOT NULL,total_limit_cents INTEGER NOT NULL,spending_paused INTEGER NOT NULL,updated_at TEXT NOT NULL);
            INSERT OR IGNORE INTO policy VALUES(1,0,0,0,1,datetime('now'));
            CREATE TABLE IF NOT EXISTS unique_events(event_key TEXT PRIMARY KEY,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS daily_jobs(denver_date TEXT PRIMARY KEY,job_id TEXT NOT NULL);
            """)

    def insert(self, collection: str, data: dict[str, Any], id: str | None = None, con: sqlite3.Connection | None = None) -> str:
        if collection not in COLLECTIONS: raise ValueError("unknown collection")
        rid, stamp = id or str(uuid.uuid4()), now()
        target = con or self.connect()
        if con:
            con.execute("INSERT INTO records VALUES(?,?,?,?,?)", (collection,rid,json.dumps(data,sort_keys=True),stamp,stamp))
        else:
            with target as c: c.execute("INSERT INTO records VALUES(?,?,?,?,?)", (collection,rid,json.dumps(data,sort_keys=True),stamp,stamp))
        return rid

    def get(self, collection: str, rid: str, con: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        if collection not in COLLECTIONS: raise ValueError("unknown collection")
        if con: row = con.execute("SELECT * FROM records WHERE collection=? AND id=?",(collection,rid)).fetchone()
        else:
            with self.connect() as c: row = c.execute("SELECT * FROM records WHERE collection=? AND id=?",(collection,rid)).fetchone()
        return ({"id":row["id"], **json.loads(row["data"])} if row else None)

    def list(self, collection: str) -> list[dict[str, Any]]:
        if collection not in COLLECTIONS: raise ValueError("unknown collection")
        with self.connect() as c: rows=c.execute("SELECT * FROM records WHERE collection=? ORDER BY created_at",(collection,)).fetchall()
        return [{"id":r["id"],**json.loads(r["data"])} for r in rows]

    def update(self, collection: str, rid: str, data: dict[str, Any], con: sqlite3.Connection) -> None:
        con.execute("UPDATE records SET data=?,updated_at=? WHERE collection=? AND id=?",(json.dumps(data,sort_keys=True),now(),collection,rid))

    def audit(self, action: str, subject: str, con: sqlite3.Connection | None=None) -> None:
        self.insert("audit", {"action":action,"subject":subject,"at":now()}, con=con)
