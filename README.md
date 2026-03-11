# macro-bias-scorer

Daily macro session bias scorer for crypto scalpers.

Scores DXY, VIX, US 10Y Yield, and Gold each morning to set your session mode before trading.

## Session Modes

| Bearish Count | Mode | Implication |
|---|---|---|
| 0-1 / 4 | LONG-BIASED | Take longs freely, shorts need extra confirmation |
| 2 / 4 | NEUTRAL | Trade both sides, reduce size, respect range |
| 3-4 / 4 | SHORT-BIASED | Take shorts freely, do not chase longs |

## Scoring Logic

Each instrument is scored BEARISH / NEUTRAL / BULLISH based on:
- 5-day momentum
- MA10 vs MA20 trend alignment
- RSI confirmation (>60 = strong up, <40 = strong down)

| Instrument | Bearish Signal |
|---|---|
| DXY | Rising (risk-off dollar strength) |
| VIX | Rising (fear increasing) |
| US 10Y Yield | Rising (tightening pressure) |
| Gold | Falling (risk-off liquidation) |

## Usage

```bash
pip install yfinance pandas rich
python macro_bias.py
```

## Output Example

```
Macro Session Bias Scorer  |  Wednesday 11 Mar 2026  19:04

  DXY (Dollar Index)   98.83   -0.35%   -0.22%   RSI 63   NEUTRAL
  VIX (Fear Index)     24.93   -2.24%   +5.77%   RSI 60   NEUTRAL
  US 10Y Yield          4.14   +0.00%   +1.97%   RSI 58   NEUTRAL
  Gold               5229.70   +2.71%   +2.39%   RSI 62   BULLISH

  SESSION MODE: LONG-BIASED  (0/4 bearish)
```

## Dependencies

- `yfinance` - Market data
- `pandas` / `numpy` - Data processing
- `rich` - Terminal formatting (optional, falls back to plain text)

## Integration

Designed to sit as a macro consensus layer on top of your existing indicator-based system (RSI, MACD, MAs). Run it pre-session, set your bias, then only take indicator signals that align with the session mode.
