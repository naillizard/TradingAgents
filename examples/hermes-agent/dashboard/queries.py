"""
Database query functions for the Hermes trading dashboard.

All functions return pandas DataFrames or plain Python types.
No Dash/Plotly imports here — pure SQLite + pandas.
"""

import os
import sqlite3
from pathlib import Path

import pandas as pd


def get_db_path() -> str:
    return os.environ.get("HERMES_DB_PATH", "/opt/data/hermes.db")


def _connect() -> sqlite3.Connection:
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_equity_curve(days: int = 90) -> pd.DataFrame:
    """
    Return daily_snapshots for the last N days.
    Columns: date, account_equity, realized_pnl, unrealized_pnl
    """
    sql = """
        SELECT date, account_equity, realized_pnl, unrealized_pnl
        FROM daily_snapshots
        WHERE date >= date('now', :offset)
        ORDER BY date ASC
    """
    offset = f"-{days} days"
    try:
        with _connect() as conn:
            df = pd.read_sql_query(sql, conn, params={"offset": offset})
    except Exception:
        df = pd.DataFrame(
            columns=["date", "account_equity", "realized_pnl", "unrealized_pnl"]
        )
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ("account_equity", "realized_pnl", "unrealized_pnl"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_open_positions() -> pd.DataFrame:
    """
    Return trades where outcome = 'open'.
    Columns: ticker, entry_price, stop_price, shares, date_open, signal, regime
    """
    sql = """
        SELECT ticker, entry_price, stop_price, shares, date_open, signal, regime
        FROM trades
        WHERE outcome = 'open'
        ORDER BY date_open DESC
    """
    try:
        with _connect() as conn:
            df = pd.read_sql_query(sql, conn)
    except Exception:
        df = pd.DataFrame(
            columns=["ticker", "entry_price", "stop_price", "shares",
                     "date_open", "signal", "regime"]
        )
    df["date_open"] = pd.to_datetime(df["date_open"], errors="coerce")
    for col in ("entry_price", "stop_price", "shares"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_recent_trades(limit: int = 10) -> pd.DataFrame:
    """
    Return the last N closed trades.
    Columns: ticker, signal, entry_price, pnl_dollars, pnl_pct, outcome, date_open, date_close
    """
    sql = """
        SELECT ticker, signal, entry_price, pnl_dollars, pnl_pct,
               outcome, date_open, date_close
        FROM trades
        WHERE outcome != 'open'
        ORDER BY date_close DESC
        LIMIT :limit
    """
    try:
        with _connect() as conn:
            df = pd.read_sql_query(sql, conn, params={"limit": limit})
    except Exception:
        df = pd.DataFrame(
            columns=["ticker", "signal", "entry_price", "pnl_dollars",
                     "pnl_pct", "outcome", "date_open", "date_close"]
        )
    for col in ("date_open", "date_close"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ("entry_price", "pnl_dollars", "pnl_pct"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_stats() -> dict:
    """
    Return a summary stats dict:
      win_rate        float 0-1
      total_trades    int
      realized_pnl    float
      unrealized_pnl  float
      account_equity  float
      account_heat    float  (sum of open position risk as fraction of equity)
    """
    defaults = {
        "win_rate": 0.0,
        "total_trades": 0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "account_equity": 0.0,
        "account_heat": 0.0,
    }
    try:
        with _connect() as conn:
            # Closed trade stats
            cur = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) AS wins
                FROM trades
                WHERE outcome NOT IN ('open', 'cancelled')
                """
            )
            row = cur.fetchone()
            total = row["total"] or 0
            wins = row["wins"] or 0
            defaults["total_trades"] = total
            defaults["win_rate"] = (wins / total) if total > 0 else 0.0

            # Latest snapshot
            cur = conn.execute(
                """
                SELECT account_equity, realized_pnl, unrealized_pnl
                FROM daily_snapshots
                ORDER BY date DESC
                LIMIT 1
                """
            )
            snap = cur.fetchone()
            if snap:
                defaults["account_equity"] = float(snap["account_equity"] or 0)
                defaults["realized_pnl"] = float(snap["realized_pnl"] or 0)
                defaults["unrealized_pnl"] = float(snap["unrealized_pnl"] or 0)

            # Account heat = sum of (entry - stop) * shares for open positions / equity
            cur = conn.execute(
                """
                SELECT entry_price, stop_price, shares
                FROM trades
                WHERE outcome = 'open'
                  AND entry_price IS NOT NULL
                  AND stop_price IS NOT NULL
                  AND shares IS NOT NULL
                """
            )
            open_rows = cur.fetchall()
            total_risk = sum(
                abs((r["entry_price"] - r["stop_price"]) * r["shares"])
                for r in open_rows
            )
            equity = defaults["account_equity"]
            defaults["account_heat"] = (total_risk / equity) if equity > 0 else 0.0

    except Exception:
        pass

    return defaults


def get_analyst_performance() -> pd.DataFrame:
    """
    Return per-analyst win rates.
    Columns: analyst_name, total_signals, wins, win_rate
    """
    sql = """
        SELECT
            analyst_name,
            COUNT(*) AS total_signals,
            SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) AS wins
        FROM analyst_performance
        GROUP BY analyst_name
        ORDER BY wins DESC
    """
    try:
        with _connect() as conn:
            df = pd.read_sql_query(sql, conn)
    except Exception:
        df = pd.DataFrame(columns=["analyst_name", "total_signals", "wins"])
    for col in ("total_signals", "wins"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["win_rate"] = df.apply(
        lambda r: r["wins"] / r["total_signals"] if r["total_signals"] > 0 else 0.0,
        axis=1,
    )
    return df


def get_trades_full() -> pd.DataFrame:
    """Return all trades for scatter/histogram analysis."""
    sql = """
        SELECT id, ticker, date_open, date_close, entry_price, stop_price,
               target_price, shares, signal, pnl_dollars, pnl_pct, outcome,
               regime, analysts_fired, scenario, actual_outcome, skill_used, notes
        FROM trades
        ORDER BY date_open DESC
    """
    try:
        with _connect() as conn:
            df = pd.read_sql_query(sql, conn)
    except Exception:
        df = pd.DataFrame()
    for col in ("date_open", "date_close"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ("entry_price", "stop_price", "target_price",
                "shares", "pnl_dollars", "pnl_pct"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_skill_library() -> list[dict]:
    """
    Read skill .md files from /opt/data/skills/.
    Returns list of {name, description, protected} dicts.
    Protected = True if the filename starts with '_'.
    """
    skills_dir = Path(os.environ.get("HERMES_SKILLS_PATH", "/opt/data/skills"))
    results = []
    if not skills_dir.is_dir():
        return results
    for md_file in sorted(skills_dir.glob("*.md")):
        protected = md_file.name.startswith("_")
        description = ""
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
            # Use first non-empty line as description
            for line in text.splitlines():
                line = line.strip().lstrip("#").strip()
                if line:
                    description = line
                    break
        except OSError:
            pass
        results.append(
            {
                "name": md_file.stem.lstrip("_"),
                "description": description,
                "protected": protected,
            }
        )
    return results
