"""
migrate_schema.py — extend Hermes' SQLite DB with trading-specific tables.

Run once via `fly ssh console` after first deploy:
    python /opt/hermes_tools/scripts/migrate_schema.py

Idempotent: safe to run multiple times.
"""

import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = "/opt/data/hermes.db"


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    print("  creating table: trades")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id              TEXT PRIMARY KEY,
            ticker          TEXT NOT NULL,
            date_open       TEXT NOT NULL,
            date_close      TEXT,
            entry_price     REAL,
            stop_price      REAL,
            target_price    REAL,
            shares          INTEGER,
            signal          TEXT,
            pnl_dollars     REAL,
            pnl_pct         REAL,
            outcome         TEXT,
            regime          TEXT,
            analysts_fired  TEXT,
            scenario        TEXT,
            actual_outcome  TEXT,
            skill_used      TEXT,
            notes           TEXT
        )
    """)

    print("  creating table: daily_snapshots")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            date            TEXT PRIMARY KEY,
            account_equity  REAL,
            open_positions  INTEGER,
            realized_pnl    REAL,
            unrealized_pnl  REAL
        )
    """)

    print("  creating table: analyst_performance")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analyst_performance (
            analyst_name    TEXT NOT NULL,
            date            TEXT NOT NULL,
            signal_fired    TEXT,
            trade_id        TEXT,
            outcome         TEXT,
            PRIMARY KEY (analyst_name, date, trade_id)
        )
    """)

    print("  creating FTS5 virtual table: trades_fts")
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS trades_fts USING fts5(
            ticker, regime, signal, scenario, analysts_fired, notes,
            content=trades, content_rowid=rowid
        )
    """)

    # FTS5 sync triggers — DROP and recreate so the body stays current
    # without needing a schema-version guard.
    print("  creating FTS5 sync triggers")

    cur.execute("DROP TRIGGER IF EXISTS trades_ai")
    cur.execute("""
        CREATE TRIGGER trades_ai AFTER INSERT ON trades BEGIN
            INSERT INTO trades_fts(rowid, ticker, regime, signal, scenario,
                                   analysts_fired, notes)
            VALUES (new.rowid, new.ticker, new.regime, new.signal,
                    new.scenario, new.analysts_fired, new.notes);
        END
    """)

    cur.execute("DROP TRIGGER IF EXISTS trades_ad")
    cur.execute("""
        CREATE TRIGGER trades_ad AFTER DELETE ON trades BEGIN
            INSERT INTO trades_fts(trades_fts, rowid, ticker, regime, signal,
                                   scenario, analysts_fired, notes)
            VALUES ('delete', old.rowid, old.ticker, old.regime, old.signal,
                    old.scenario, old.analysts_fired, old.notes);
        END
    """)

    cur.execute("DROP TRIGGER IF EXISTS trades_au")
    cur.execute("""
        CREATE TRIGGER trades_au AFTER UPDATE ON trades BEGIN
            INSERT INTO trades_fts(trades_fts, rowid, ticker, regime, signal,
                                   scenario, analysts_fired, notes)
            VALUES ('delete', old.rowid, old.ticker, old.regime, old.signal,
                    old.scenario, old.analysts_fired, old.notes);
            INSERT INTO trades_fts(rowid, ticker, regime, signal, scenario,
                                   analysts_fired, notes)
            VALUES (new.rowid, new.ticker, new.regime, new.signal,
                    new.scenario, new.analysts_fired, new.notes);
        END
    """)

    conn.commit()
    print("  migration complete.")


# ---------------------------------------------------------------------------
# Helper functions importable by other modules
# ---------------------------------------------------------------------------

def record_trade(conn: sqlite3.Connection, trade_dict: dict) -> None:
    """Insert a new trade row. trade_dict must include at minimum 'id',
    'ticker', and 'date_open'. analysts_fired will be JSON-encoded if passed
    as a list."""
    row = dict(trade_dict)
    if isinstance(row.get("analysts_fired"), list):
        row["analysts_fired"] = json.dumps(row["analysts_fired"])
    if "date_open" not in row:
        row["date_open"] = datetime.now(timezone.utc).isoformat()

    columns = ", ".join(row.keys())
    placeholders = ", ".join(f":{k}" for k in row.keys())
    conn.execute(
        f"INSERT OR REPLACE INTO trades ({columns}) VALUES ({placeholders})",
        row,
    )
    conn.commit()


def record_close(
    conn: sqlite3.Connection,
    trade_id: str,
    pnl_dollars: float,
    pnl_pct: float,
    outcome: str,
    actual_outcome: str,
) -> None:
    """Mark an open trade as closed with its P&L and outcome."""
    conn.execute(
        """
        UPDATE trades
        SET date_close    = :date_close,
            pnl_dollars   = :pnl_dollars,
            pnl_pct       = :pnl_pct,
            outcome       = :outcome,
            actual_outcome = :actual_outcome
        WHERE id = :id
        """,
        {
            "id": trade_id,
            "date_close": datetime.now(timezone.utc).isoformat(),
            "pnl_dollars": pnl_dollars,
            "pnl_pct": pnl_pct,
            "outcome": outcome,
            "actual_outcome": actual_outcome,
        },
    )
    conn.commit()


if __name__ == "__main__":
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    print(f"connecting to {db_path}")
    with _connect(db_path) as conn:
        migrate(conn)
    print("done.")
