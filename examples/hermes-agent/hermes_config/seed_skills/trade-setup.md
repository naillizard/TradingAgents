---
name: trade-setup
description: >
  Standard trade setup evaluation checklist. Applied before every
  TradingAgents analysis to confirm the setup meets minimum quality bars.
protected: false
---

# Trade Setup Checklist

Before proposing a trade, verify all of the following:

## Signal Quality
- At least two independent analysts agree on direction (Buy/Sell).
- Confidence score ≥ 55%.
- No conflicting signals from fundamentals + technical simultaneously.

## Risk Parameters
- Entry price clearly identified (limit, not market).
- Stop-loss defined: maximum 5% below entry for long setups.
- Risk/reward ratio ≥ 1.5:1 (target at least 1.5× the stop distance).
- Position size ≤ 1% of account equity at risk (hardcoded — see risk-rules.md).

## Regime Check
- Confirm macro regime from `market_data_tool` before acting on signal.
- Avoid initiating new longs in a Contracting / Bear regime unless explicitly
  overridden by a strong playbook skill.

## Timing
- Do not trade within 30 minutes of major economic releases (CPI, FOMC, NFP).
- Prefer entries during regular market hours (09:30–16:00 ET).

## Memory Enrichment
- Run FTS5 query: `ticker + regime + signal` before sending approval card.
- Include historical win rate in the Telegram card if ≥ 5 similar trades found.
