"""
Hermes tool: ib_executor_tool
Connects to IB Gateway and manages the full order lifecycle.

Dependencies: ib_insync
Connects to: host:port configured via IB_GATEWAY_HOST / IB_GATEWAY_PORT env vars.
Default port 4002 = paper trading. Flip to 4001 for live.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

IB_HOST = os.environ.get("IB_GATEWAY_HOST", "127.0.0.1")
IB_PORT = int(os.environ.get("IB_GATEWAY_PORT", "4002"))
IB_CLIENT_ID = int(os.environ.get("IB_CLIENT_ID", "1"))
IB_ACCOUNT = os.environ.get("IB_ACCOUNT_ID", "")

# Callback registry — populated by Hermes after tool registration.
_on_fill: Optional[Callable] = None
_on_close: Optional[Callable] = None


def set_fill_callback(fn: Callable) -> None:
    """Register a callback invoked when an order fills."""
    global _on_fill
    _on_fill = fn


def set_close_callback(fn: Callable) -> None:
    """Register a callback invoked when a position closes (stop hit / target reached)."""
    global _on_close
    _on_close = fn


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _get_ib():
    """Return a connected IB instance, retrying with exponential backoff."""
    try:
        from ib_insync import IB
    except ImportError as exc:
        raise RuntimeError(
            "ib_insync not installed. Add it to requirements or: pip install ib_insync"
        ) from exc

    ib = IB()
    delay = 2
    for attempt in range(5):
        try:
            ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
            logger.info("IB Gateway connected: %s:%s", IB_HOST, IB_PORT)
            return ib
        except Exception as exc:  # noqa: BLE001
            logger.warning("IB connect attempt %d failed: %s", attempt + 1, exc)
            if attempt < 4:
                time.sleep(delay)
                delay = min(delay * 2, 60)
    raise ConnectionError(f"Cannot connect to IB Gateway at {IB_HOST}:{IB_PORT}")


# ---------------------------------------------------------------------------
# Exposed Hermes tools
# ---------------------------------------------------------------------------

def ib_place_bracket(
    ticker: str,
    shares: int,
    entry: float,
    stop: float,
    target: Optional[float] = None,
) -> dict:
    """
    Place a bracket order: LMT buy entry + STP stop (+ optional LMT target).

    Returns:
        {"order_id": int, "status": str, "entry": float, "stop": float}
    """
    from ib_insync import Stock, LimitOrder, StopOrder, BracketOrder

    ib = _get_ib()
    try:
        contract = Stock(ticker, "SMART", "USD")
        ib.qualifyContracts(contract)

        # Duplicate-order guard: abort if we already have an open order for this ticker
        open_orders = ib.openOrders()
        for o in open_orders:
            if hasattr(o, "contract") and o.contract.symbol == ticker:
                logger.warning("Duplicate order guard triggered for %s — skipping", ticker)
                return {"error": f"Open order already exists for {ticker}", "skipped": True}

        bracket = ib.bracketOrder(
            action="BUY",
            quantity=shares,
            limitPrice=entry,
            takeProfitPrice=target or (entry + (entry - stop) * 2),  # default 2:1 R
            stopLossPrice=stop,
        )

        for order in bracket:
            ib.placeOrder(contract, order)

        parent_id = bracket[0].orderId
        logger.info(
            "Bracket placed: ticker=%s shares=%d entry=%.2f stop=%.2f order_id=%d",
            ticker, shares, entry, stop, parent_id,
        )
        return {
            "order_id": parent_id,
            "status": "submitted",
            "ticker": ticker,
            "shares": shares,
            "entry": entry,
            "stop": stop,
        }
    finally:
        ib.disconnect()


def ib_cancel_order(order_id: int) -> dict:
    """Cancel an open order by ID."""
    from ib_insync import Trade

    ib = _get_ib()
    try:
        open_trades = ib.openTrades()
        for trade in open_trades:
            if trade.order.orderId == order_id:
                ib.cancelOrder(trade.order)
                logger.info("Cancelled order %d", order_id)
                return {"order_id": order_id, "status": "cancelled"}
        return {"order_id": order_id, "status": "not_found"}
    finally:
        ib.disconnect()


def ib_get_positions() -> list[dict]:
    """Return all open positions."""
    ib = _get_ib()
    try:
        positions = ib.positions(account=IB_ACCOUNT)
        return [
            {
                "ticker": p.contract.symbol,
                "shares": p.position,
                "avg_cost": p.avgCost,
                "market_value": p.marketValue if hasattr(p, "marketValue") else None,
            }
            for p in positions
        ]
    finally:
        ib.disconnect()


def ib_get_account_value() -> dict:
    """Return current account equity (used for position sizing)."""
    ib = _get_ib()
    try:
        values = {
            v.tag: float(v.value)
            for v in ib.accountValues(account=IB_ACCOUNT)
            if v.currency == "USD" and v.tag in (
                "NetLiquidation", "TotalCashValue", "UnrealizedPnL", "RealizedPnL"
            )
        }
        return values
    finally:
        ib.disconnect()


# ---------------------------------------------------------------------------
# Async fill / close monitoring (started by Hermes on tool registration)
# ---------------------------------------------------------------------------

def start_monitor(notify_fn: Callable[[str, dict], None]) -> None:
    """
    Start a background thread that monitors IB for fill and close events.
    notify_fn(event_type, payload) is called on fill/close.
    """
    def _run():
        from ib_insync import IB, util

        ib = _get_ib()

        def on_order_status(trade):
            status = trade.orderStatus.status
            if status == "Filled":
                payload = {
                    "order_id": trade.order.orderId,
                    "ticker": trade.contract.symbol,
                    "shares": trade.order.totalQuantity,
                    "avg_fill": trade.orderStatus.avgFillPrice,
                }
                logger.info("Fill event: %s", payload)
                notify_fn("fill", payload)
                if _on_fill:
                    _on_fill(payload)
            elif status in ("Cancelled", "Inactive"):
                payload = {
                    "order_id": trade.order.orderId,
                    "ticker": trade.contract.symbol,
                    "status": status,
                }
                logger.info("Close/cancel event: %s", payload)
                notify_fn("close", payload)
                if _on_close:
                    _on_close(payload)

        ib.orderStatusEvent += on_order_status

        try:
            util.run()  # blocks — IB event loop
        except Exception as exc:  # noqa: BLE001
            logger.error("IB monitor crashed: %s — sending alert", exc)
            notify_fn("error", {"message": f"IB Gateway disconnected: {exc}"})

    thread = threading.Thread(target=_run, daemon=True, name="ib-monitor")
    thread.start()
    logger.info("IB monitor thread started")
