"""
register_tools.py — register custom trading tools with the Hermes tool registry.

Run once via `fly ssh console` after first deploy:
    python /opt/hermes_tools/scripts/register_tools.py

Idempotent: uses INSERT OR REPLACE so re-running updates descriptions in place.
"""

import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

DB_PATH = "/opt/data/hermes.db"

TOOLS = [
    {
        "name": "tradingagents_tool",
        "module": "/opt/hermes_tools/tradingagents_tool.py",
        "description": (
            "Run full TradingAgents multi-agent analysis on a ticker. "
            "Returns TraderProposal."
        ),
    },
    {
        "name": "ib_executor_tool",
        "module": "/opt/hermes_tools/ib_executor_tool.py",
        "description": (
            "Connect to IB Gateway and manage bracket orders. "
            "Paper trading default (port 4002)."
        ),
    },
    {
        "name": "telegram_tool",
        "module": "/opt/hermes_tools/telegram_tool.py",
        "description": (
            "Send trade approval cards and notifications via Telegram. "
            "HITL touchpoint."
        ),
    },
]


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_tools_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tools (
            name            TEXT PRIMARY KEY,
            module          TEXT NOT NULL,
            description     TEXT,
            registered_at   TEXT NOT NULL
        )
    """)
    conn.commit()


def register_via_db(conn: sqlite3.Connection) -> list[str]:
    """Insert / update tool rows in the DB registry. Returns list of names."""
    now = datetime.now(timezone.utc).isoformat()
    registered = []
    for tool in TOOLS:
        conn.execute(
            """
            INSERT OR REPLACE INTO tools (name, module, description, registered_at)
            VALUES (:name, :module, :description, :registered_at)
            """,
            {**tool, "registered_at": now},
        )
        registered.append(tool["name"])
        print(f"  [db]  registered: {tool['name']}")
    conn.commit()
    return registered


def register_via_cli() -> None:
    """Attempt to register tools through the `hermes tool register` CLI.
    Logs a warning and continues if the binary is not found."""
    for tool in TOOLS:
        cmd = [
            "hermes", "tool", "register",
            "--name", tool["name"],
            "--module", tool["module"],
            "--description", tool["description"],
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                print(f"  [cli] registered: {tool['name']}")
            else:
                stderr = result.stderr.strip()
                print(
                    f"  [cli] warning: hermes returned non-zero for "
                    f"{tool['name']}: {stderr or '(no output)'}"
                )
        except FileNotFoundError:
            print(
                "  [cli] warning: 'hermes' binary not found — "
                "skipping CLI registration (DB registration still applied)"
            )
            return  # no point trying remaining tools
        except subprocess.TimeoutExpired:
            print(
                f"  [cli] warning: hermes CLI timed out for {tool['name']} — "
                "skipping"
            )


def print_summary(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT name, module, registered_at FROM tools ORDER BY name"
    ).fetchall()
    print("\nregistered tools in DB:")
    print(f"  {'name':<25} {'module':<50} registered_at")
    print(f"  {'-'*24} {'-'*49} {'-'*27}")
    for row in rows:
        print(f"  {row['name']:<25} {row['module']:<50} {row['registered_at']}")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    print(f"connecting to {db_path}")

    with _connect(db_path) as conn:
        print("ensuring tools table exists")
        ensure_tools_table(conn)

        print("registering via DB:")
        register_via_db(conn)

        print("attempting CLI registration:")
        register_via_cli()

        print_summary(conn)

    print("\ndone.")
