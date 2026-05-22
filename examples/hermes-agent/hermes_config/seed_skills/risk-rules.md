---
name: risk-rules
description: >
  Core risk management rules. PROTECTED — Hermes may NOT auto-edit this file,
  even if self-improvement logic would otherwise rewrite a skill.
protected: true
---

# Risk Rules — Protected

These rules are invariants. They cannot be overridden by playbook skills,
operator prompts, or self-improvement logic.

## Position Sizing
- **Maximum risk per trade: 1% of current account equity.**
  - Example: $100k account → maximum $1,000 at risk per trade.
  - Position size = risk_dollars / (entry_price − stop_price).
- Never exceed 5% of account in a single position (market value).
- Never hold more than 20% of account in positions from the same sector.

## Stop Losses
- Every trade MUST have a hard stop-loss order placed at IB simultaneously
  with the entry order (bracket order pattern).
- Stop placement: determined by TradingAgents analysis. Never tighter than
  the instrument's 1-day ATR; never wider than 8% from entry.

## Order Types
- Entry: Limit order only. No market orders.
- Stop: Stop order (STP). No mental stops.
- Target: Limit order (optional — included in bracket when confidence ≥ 70%).

## Trade Frequency
- Maximum 3 open positions simultaneously during prototype phase.
- Maximum 1 new position per trading day unless a playbook skill explicitly
  qualifies a second setup.

## Account Protection
- If account drawdown from peak exceeds 5% in any rolling 20-day period:
  halt new trades and notify operator via Telegram.
- If IB Gateway connection is lost: do not initiate new orders. Alert operator.

## Live Trading
- Default: paper trading (IB port 4002).
- Switching to live (port 4001) requires explicit operator confirmation via
  Telegram AND manual update of IB_GATEWAY_PORT secret via `fly secrets set`.
  Hermes may not initiate this switch autonomously.
