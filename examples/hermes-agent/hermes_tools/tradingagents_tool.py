"""
Hermes tool: tradingagents_tool
Wraps TradingAgentsGraph.propagate() as a Hermes-callable tool.

Registered with Hermes via: python /opt/scripts/register_tools.py
LLM backend is whichever provider Hermes has configured at runtime —
this code is LLM-agnostic.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# TradingAgents is installed into the persistent volume on first use.
# Hermes bootstraps: git clone + uv pip install -e /opt/data/ta
TA_PATH = os.environ.get("TA_PATH", "/opt/data/ta")
if TA_PATH not in sys.path:
    sys.path.insert(0, TA_PATH)


def tradingagents_analyze(ticker: str, date: str = "latest") -> dict:
    """
    Run full TradingAgents multi-agent analysis on a ticker.

    Args:
        ticker: Stock symbol (e.g. "AAPL", "NVDA").
        date:   Analysis date as "YYYY-MM-DD", or "latest" for today.

    Returns:
        TraderProposal dict with keys:
            entry_price, stop_loss, position_sizing,
            signal (Buy/Hold/Sell), scenario,
            analysts_fired, confidence, regime, date.
    """
    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
    except ImportError as exc:
        raise RuntimeError(
            f"TradingAgents not installed at {TA_PATH}. "
            "Run the bootstrap sequence first."
        ) from exc

    analysis_date = datetime.today().strftime("%Y-%m-%d") if date == "latest" else date

    config = {**DEFAULT_CONFIG}
    # Respect env-var overrides for LLM provider (set by Hermes at runtime)
    if llm_provider := os.environ.get("LLM_PROVIDER"):
        config["llm_provider"] = llm_provider
    if llm_model := os.environ.get("LLM_MODEL"):
        config["deep_think_llm"] = llm_model
        config["quick_think_llm"] = llm_model

    graph = TradingAgentsGraph(
        selected_analysts=["market", "social", "news", "fundamentals"],
        config=config,
        debug=False,
    )

    logger.info("Starting TradingAgents analysis: ticker=%s date=%s", ticker, analysis_date)
    final_state, signal = graph.propagate(ticker, analysis_date)
    logger.info("Analysis complete: signal=%s", signal)

    return _serialize_proposal(ticker, analysis_date, final_state, signal)


def _serialize_proposal(
    ticker: str,
    date: str,
    state: Any,
    signal: str,
) -> dict:
    """Extract a structured TraderProposal from the LangGraph final state."""
    # TradingAgentsGraph populates these keys in the final AgentState dict.
    # All .get() calls default gracefully — Hermes can still act on partial data.
    messages = state.get("messages", [])
    last_msg = messages[-1].content if messages else ""

    return {
        "ticker": ticker,
        "date": date,
        "signal": signal,  # "Buy" | "Hold" | "Sell"
        "entry_price": state.get("entry_price"),
        "stop_loss": state.get("stop_loss"),
        "target_price": state.get("target_price"),
        "position_sizing": state.get("position_sizing"),
        "confidence": state.get("confidence"),
        "scenario": state.get("scenario", last_msg[:500] if last_msg else None),
        "regime": state.get("market_regime"),
        "analysts_fired": _extract_analysts(state),
        "raw_state_keys": list(state.keys()) if hasattr(state, "keys") else [],
    }


def _extract_analysts(state: Any) -> list[str]:
    """Best-effort extraction of which analysts contributed."""
    fired = []
    for key in ("market_report", "social_report", "news_report", "fundamentals_report"):
        if state.get(key):
            fired.append(key.replace("_report", ""))
    return fired or ["market", "news", "fundamentals", "social"]
