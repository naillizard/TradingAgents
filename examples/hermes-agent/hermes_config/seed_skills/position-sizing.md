---
name: position-sizing
description: >
  Position sizing algorithm. Calculates share count from account equity,
  entry price, and stop-loss price using fixed fractional (1% risk) method.
protected: false
---

# Position Sizing — Fixed Fractional (1% Risk)

## Formula

```
risk_per_trade = account_equity × 0.01          # 1% hard cap (risk-rules.md)
stop_distance  = entry_price − stop_price        # per share risk
shares         = floor(risk_per_trade / stop_distance)
```

## Example

```
Account equity:  $99,000
Entry price:     $185.00
Stop price:      $178.50
Stop distance:   $6.50

Risk per trade:  $990
Shares:          floor(990 / 6.50) = 152 shares
Position value:  152 × $185.00 = $28,120  (28.4% of account — flag if > 20%)
```

## Adjustments

- **Volatility scaling (optional):** If the instrument's 14-day ATR is more
  than 2× its historical average, reduce shares by 25% to account for
  elevated volatility.
- **Confidence scaling (optional):** If analyst confidence < 55%, reduce
  shares to 50% of calculated size.
- **Sector concentration:** If adding this position would take sector
  exposure above 20% of account, reduce to fit within the cap.

## Output

Return a dict with:
```python
{
    "shares": int,
    "risk_dollars": float,
    "position_value": float,
    "risk_pct": float,          # should be ≤ 1.0
    "account_equity": float,
}
```
