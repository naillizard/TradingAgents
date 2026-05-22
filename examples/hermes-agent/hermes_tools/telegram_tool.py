"""
Hermes tool: telegram_tool
Single human touchpoint for HITL approval and notifications.

Dependencies: python-telegram-bot>=20
Security: responds only to TELEGRAM_ALLOWED_USER_ID (set via fly secrets).
Timeout: APPROVAL_TIMEOUT_MINUTES (default 30) → auto-reject.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID = int(os.environ.get("TELEGRAM_ALLOWED_USER_ID", "0"))
APPROVAL_TIMEOUT = int(os.environ.get("APPROVAL_TIMEOUT_MINUTES", "30")) * 60

# Active approval sessions: trade_id → asyncio.Future
_pending: dict[str, asyncio.Future] = {}
_loop: Optional[asyncio.AbstractEventLoop] = None
_app = None  # telegram.ext.Application


# ---------------------------------------------------------------------------
# Exposed Hermes tools
# ---------------------------------------------------------------------------

def telegram_send_approval(trade_card: dict) -> dict:
    """
    Send a trade approval card with ✅/❌/📊 inline buttons.
    Blocks until the user responds or APPROVAL_TIMEOUT_MINUTES elapses.

    Args:
        trade_card: TraderProposal dict from tradingagents_tool.

    Returns:
        {"approved": bool, "trade_id": str, "responded_at": str | None}
    """
    _ensure_bot_running()

    trade_id = trade_card.get("ticker", "UNKNOWN") + "_" + datetime.utcnow().strftime("%H%M%S")
    text = _format_card(trade_card)
    keyboard = _approval_keyboard(trade_id)

    future = _loop.call_soon_threadsafe(_register_pending, trade_id)

    # Send the card
    asyncio.run_coroutine_threadsafe(
        _send_message(text, reply_markup=keyboard),
        _loop,
    ).result(timeout=10)

    # Block until response or timeout
    future_obj = _pending[trade_id]
    try:
        approved = asyncio.run_coroutine_threadsafe(
            asyncio.wait_for(asyncio.shield(future_obj), timeout=APPROVAL_TIMEOUT),
            _loop,
        ).result(timeout=APPROVAL_TIMEOUT + 5)
    except (asyncio.TimeoutError, TimeoutError):
        logger.info("Approval timed out for %s — auto-rejecting", trade_id)
        asyncio.run_coroutine_threadsafe(
            _send_message(f"⏰ No response for {trade_id} — auto-rejected."),
            _loop,
        )
        approved = False
        _pending.pop(trade_id, None)

    return {
        "approved": approved,
        "trade_id": trade_id,
        "responded_at": datetime.utcnow().isoformat() if approved is not None else None,
    }


def telegram_notify(message: str, level: str = "info") -> None:
    """
    Send a notification message (fills, stops, errors, summaries).

    Args:
        message: Plain text or Markdown message body.
        level:   "info" | "warning" | "alert"
    """
    _ensure_bot_running()
    icons = {"info": "ℹ️", "warning": "⚠️", "alert": "🚨"}
    icon = icons.get(level, "ℹ️")
    text = f"{icon} {message}"
    asyncio.run_coroutine_threadsafe(
        _send_message(text),
        _loop,
    ).result(timeout=10)


# ---------------------------------------------------------------------------
# Card formatting
# ---------------------------------------------------------------------------

def _format_card(card: dict) -> str:
    ticker = card.get("ticker", "—")
    signal = card.get("signal", "—")
    entry = card.get("entry_price")
    stop = card.get("stop_loss")
    shares = card.get("position_sizing", {})
    if isinstance(shares, dict):
        n_shares = shares.get("shares", "—")
        risk_dollars = shares.get("risk_dollars", "—")
        account = shares.get("account_equity", None)
    else:
        n_shares = "—"
        risk_dollars = "—"
        account = None

    stop_pct = ""
    if entry and stop and entry > 0:
        stop_pct = f"  (−{abs(entry - stop) / entry * 100:.1f}%)"

    risk_pct = ""
    if risk_dollars and account and account > 0:
        risk_pct = f"  ({risk_dollars / account * 100:.1f}% of ${account:,.0f})"

    regime = card.get("regime") or "—"
    scenario = (card.get("scenario") or "—")[:200]
    confidence = card.get("confidence")
    conf_str = f"{confidence:.0%}" if confidence else "—"

    lines = [
        f"📊 *TRADE SETUP — {ticker}*",
        "",
        f"Direction:  *{signal.upper()}*",
        f"Entry:      ${entry:.2f}" if entry else "Entry:      —",
        f"Stop:       ${stop:.2f}{stop_pct}" if stop else "Stop:       —",
        f"Shares:     {n_shares}",
        f"Risk:       ${risk_dollars}{risk_pct}" if risk_dollars != "—" else "Risk:       —",
        "",
        f"Confidence: {conf_str}",
        f"Regime:     {regime}",
        f"Signal:     {scenario}",
    ]
    return "\n".join(lines)


def _approval_keyboard(trade_id: str):
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        return None

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{trade_id}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"reject:{trade_id}"),
            InlineKeyboardButton("📊 More Info", callback_data=f"info:{trade_id}"),
        ]
    ])


# ---------------------------------------------------------------------------
# Bot internals
# ---------------------------------------------------------------------------

def _register_pending(trade_id: str) -> asyncio.Future:
    future = _loop.create_future()
    _pending[trade_id] = future
    return future


async def _send_message(text: str, reply_markup=None) -> None:
    if not _app:
        logger.error("Telegram bot not initialised — cannot send: %s", text[:80])
        return
    await _app.bot.send_message(
        chat_id=ALLOWED_USER_ID,
        text=text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


def _ensure_bot_running() -> None:
    global _loop, _app
    if _app is not None:
        return

    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env var not set.")
    if not ALLOWED_USER_ID:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_ID env var not set.")

    started = threading.Event()

    def _run_bot():
        global _loop, _app
        from telegram.ext import Application, CallbackQueryHandler

        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)

        _app = Application.builder().token(BOT_TOKEN).build()
        _app.add_handler(CallbackQueryHandler(_handle_button))

        async def _start():
            await _app.initialize()
            await _app.start()
            await _app.updater.start_polling(drop_pending_updates=True)
            started.set()
            # Keep running
            await asyncio.Event().wait()

        _loop.run_until_complete(_start())

    thread = threading.Thread(target=_run_bot, daemon=True, name="telegram-bot")
    thread.start()
    started.wait(timeout=15)
    if not _app:
        raise RuntimeError("Telegram bot failed to start within 15 s.")
    logger.info("Telegram bot started, listening for user %d", ALLOWED_USER_ID)


async def _handle_button(update, context) -> None:
    """Handle inline button callbacks from the approval card."""
    query = update.callback_query
    user_id = query.from_user.id

    # Security: ignore anyone other than the configured operator
    if user_id != ALLOWED_USER_ID:
        await query.answer("Unauthorised.")
        return

    await query.answer()
    data = query.data  # e.g. "approve:AAPL_143022"
    action, trade_id = data.split(":", 1)

    if action == "info":
        # Expand with more detail (future: pull from memory)
        await query.edit_message_text(
            query.message.text + "\n\n📋 _Full analyst signals stored in Hermes memory._",
            parse_mode="Markdown",
        )
        return

    future = _pending.pop(trade_id, None)
    if future and not future.done():
        approved = action == "approve"
        future.get_loop().call_soon_threadsafe(future.set_result, approved)
        label = "✅ Approved" if approved else "❌ Rejected"
        await query.edit_message_text(f"{query.message.text}\n\n{label}", parse_mode="Markdown")
        logger.info("Trade %s %s by user %d", trade_id, label.lower(), user_id)
    else:
        await query.edit_message_text("⚠️ This approval has already been resolved.")
