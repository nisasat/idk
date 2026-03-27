"""
ORB Trading Bot — Live / Paper-Trade Runner

This is the main entry point for running the ORB strategy in real-time.
It polls for new 1-minute candle data, evaluates the ORB setup, and
logs signals.  Actual order execution should be wired to your broker's
API (not included — see the `execute_trade` stub).

Usage:
    python bot.py                     # paper-trade mode (default)
    python bot.py --live              # live mode (requires broker integration)
"""

import argparse
import time
from datetime import datetime

import pandas as pd
import pytz

import config
from indicators import compute_atr, compute_vwap
from orb_strategy import ORBStrategy, TradeSignal
from premarket import analyse_premarket


# ── Broker stub ─────────────────────────────────────────────────────────────

def fetch_latest_bars(symbol: str, interval: str, lookback_bars: int) -> pd.DataFrame:
    """
    Replace this stub with your broker / data-feed integration.

    Must return a DataFrame with columns:
        open, high, low, close, volume
    and a tz-aware DatetimeIndex.
    """
    raise NotImplementedError(
        "Implement fetch_latest_bars() with your data provider "
        "(e.g. Interactive Brokers, Tradovate, Alpaca, Polygon.io)."
    )


def execute_trade(signal: TradeSignal, live: bool = False) -> None:
    """
    Replace this stub with your broker's order API.

    In paper mode, just log the signal.
    """
    mode = "LIVE" if live else "PAPER"
    print(f"\n{'=' * 60}")
    print(f"  [{mode}] NEW SIGNAL")
    print(f"  {signal}")
    print(f"{'=' * 60}\n")


# ── Main loop ───────────────────────────────────────────────────────────────

def run_bot(symbol: str = "ES", live: bool = False) -> None:
    eastern = pytz.timezone(config.TIMEZONE)
    print(f"ORB Bot started — {'LIVE' if live else 'PAPER'} mode")
    print(f"  Symbol         : {symbol}")
    print(f"  ORB candle     : {config.ORB_CANDLE_TIME} EST")
    print(f"  VWAP bias      : {'ON' if config.REQUIRE_VWAP_BIAS else 'OFF'}")
    print(f"  ATR filter     : {config.ATR_MIN_MULTIPLIER}x – {config.ATR_MAX_MULTIPLIER}x")
    print(f"  Risk:Reward    : 1:{config.RISK_REWARD_RATIO}")
    print(f"  Max trades/day : {config.MAX_TRADES_PER_DAY}")
    print()

    fired_today: list[TradeSignal] = []
    last_date: str = ""

    while True:
        now = datetime.now(eastern)
        today_str = now.strftime("%Y-%m-%d")

        # Reset state on new day
        if today_str != last_date:
            fired_today = []
            last_date = today_str
            print(f"── New session: {today_str} ──")

        # Only run between trading start and end
        current_time = now.strftime("%H:%M")
        if current_time < config.TRADING_START or current_time > config.TRADING_END:
            time.sleep(30)
            continue

        if len(fired_today) >= config.MAX_TRADES_PER_DAY:
            time.sleep(60)
            continue

        # Fetch data
        try:
            df = fetch_latest_bars(symbol, config.CANDLE_INTERVAL, lookback_bars=500)
        except NotImplementedError as e:
            print(f"[ERROR] {e}")
            print("Exiting. Please implement fetch_latest_bars() in bot.py.")
            return
        except Exception as e:
            print(f"[WARN] Data fetch failed: {e}")
            time.sleep(10)
            continue

        # Run strategy
        strategy = ORBStrategy()
        signals = strategy.run(df)

        for sig in signals:
            # Avoid duplicate signals
            already_fired = any(
                s.direction == sig.direction and s.entry_time == sig.entry_time
                for s in fired_today
            )
            if already_fired:
                continue

            execute_trade(sig, live=live)
            fired_today.append(sig)

        # Poll every 30 seconds
        time.sleep(30)


# ── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ORB Futures Trading Bot")
    parser.add_argument("--symbol", default="ES", help="Futures symbol (default: ES)")
    parser.add_argument("--live", action="store_true", help="Enable live trading mode")
    args = parser.parse_args()
    run_bot(symbol=args.symbol, live=args.live)


if __name__ == "__main__":
    main()
