# ORB Futures Trading Bot

Intraday trading bot for futures based on the **Opening Range Breakout (ORB)** setup.

## Strategy

1. **ORB Candle**: The 9:35 AM EST 1-minute candle defines the Opening Range. Its high and low (including wicks) are marked as breakout levels.
2. **Breakout Confirmation**: After the ORB candle closes, the bot waits for a *strong* candle (body ≥ 50% of total range) to close above the ORB high (long) or below the ORB low (short).
3. **VWAP Directional Bias**: Long entries require VWAP to be above the ORB high; short entries require VWAP below the ORB low.
4. **ATR Filter**: The ORB range must fall within 0.5x–2.0x of the ATR to filter out noise and over-extended days.
5. **Premarket Context**: Pre-market volume must exceed a threshold for the session to be considered valid.

## Files

| File | Purpose |
|---|---|
| `config.py` | All tunable parameters (timing, filters, risk management) |
| `indicators.py` | VWAP and ATR calculations |
| `premarket.py` | Pre-market session analysis |
| `orb_strategy.py` | Core ORB strategy logic and signal generation |
| `backtest.py` | Backtesting harness — run against historical CSV data |
| `bot.py` | Live/paper-trade runner (requires broker data feed) |

## Quick Start

```bash
pip install -r requirements.txt

# Backtest with historical 1-min data
python backtest.py data/ES_1min.csv

# Paper trade (implement fetch_latest_bars in bot.py first)
python bot.py --symbol ES

# Live trade
python bot.py --symbol ES --live
```

## CSV Format

The backtest expects a CSV with columns: `datetime, open, high, low, close, volume`.

## Configuration

All parameters are in `config.py`. Key settings:

- `ORB_CANDLE_TIME` — the candle that defines the opening range (default: 09:35)
- `MIN_BODY_RATIO` — minimum candle body ratio for breakout confirmation
- `REQUIRE_VWAP_BIAS` — toggle VWAP directional filter
- `ATR_PERIOD` / `ATR_MIN_MULTIPLIER` / `ATR_MAX_MULTIPLIER` — ATR filter bounds
- `RISK_REWARD_RATIO` — target distance as multiple of risk
- `MAX_TRADES_PER_DAY` — daily trade cap
