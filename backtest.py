"""
Backtesting harness for the ORB strategy.

Reads historical 1-minute bar data (CSV), runs the strategy day-by-day,
and prints a summary with per-trade details.

CSV format expected:
    datetime, open, high, low, close, volume
    (datetime in ISO format or any pandas-parseable format, preferably UTC)
"""

import sys
from pathlib import Path

import pandas as pd
import pytz

import config
from indicators import compute_atr
from orb_strategy import ORBStrategy, TradeSignal


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["datetime"], index_col="datetime")
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    df.sort_index(inplace=True)
    return df


def split_by_day(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    eastern = pytz.timezone(config.TIMEZONE)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(eastern)
    grouped = {}
    for date, group in df.groupby(df.index.date):
        grouped[str(date)] = group
    return grouped


def simulate_trade(signal: TradeSignal, day_df: pd.DataFrame) -> dict:
    """
    Walk forward from the entry candle and determine outcome:
    hit stop, hit target, or end-of-day exit.
    """
    bars_after = day_df.loc[day_df.index > signal.entry_time]

    for ts, bar in bars_after.iterrows():
        if signal.direction == "LONG":
            if bar["low"] <= signal.stop_loss:
                return {"outcome": "STOP", "exit_price": signal.stop_loss, "exit_time": ts}
            if bar["high"] >= signal.take_profit:
                return {"outcome": "TARGET", "exit_price": signal.take_profit, "exit_time": ts}
        else:
            if bar["high"] >= signal.stop_loss:
                return {"outcome": "STOP", "exit_price": signal.stop_loss, "exit_time": ts}
            if bar["low"] <= signal.take_profit:
                return {"outcome": "TARGET", "exit_price": signal.take_profit, "exit_time": ts}

    # End-of-day flat exit
    last_close = day_df["close"].iloc[-1]
    return {"outcome": "EOD", "exit_price": last_close, "exit_time": day_df.index[-1]}


def compute_daily_atr(df: pd.DataFrame) -> pd.Series:
    """Resample to daily bars and compute ATR for lookback context."""
    daily = df.resample("1D").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    return compute_atr(daily, period=config.ATR_PERIOD)


def run_backtest(csv_path: str) -> None:
    print(f"Loading data from {csv_path} …")
    df = load_data(csv_path)
    print(f"  Loaded {len(df):,} bars from {df.index[0]} → {df.index[-1]}")

    daily_atr_series = compute_daily_atr(df)
    days = split_by_day(df)

    all_trades: list[dict] = []

    for date_str, day_df in sorted(days.items()):
        # Look up prior-day ATR if available
        atr_val = None
        if not daily_atr_series.empty:
            prior = daily_atr_series.loc[daily_atr_series.index < date_str]
            if not prior.empty:
                atr_val = prior.iloc[-1]

        strategy = ORBStrategy(daily_atr=atr_val)
        signals = strategy.run(day_df)

        for sig in signals:
            result = simulate_trade(sig, day_df)
            pnl = (
                (result["exit_price"] - sig.entry_price)
                if sig.direction == "LONG"
                else (sig.entry_price - result["exit_price"])
            )
            trade = {
                "date": date_str,
                "direction": sig.direction,
                "entry": sig.entry_price,
                "stop": sig.stop_loss,
                "target": sig.take_profit,
                "exit": result["exit_price"],
                "outcome": result["outcome"],
                "pnl": pnl,
                "entry_time": sig.entry_time,
                "exit_time": result["exit_time"],
                "vwap": sig.vwap_at_entry,
                "atr": sig.atr_value,
            }
            all_trades.append(trade)
            print(f"  {date_str} | {sig.direction:5s} | {result['outcome']:6s} | PnL: {pnl:+.2f}")

    # ── Summary ─────────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    if not all_trades:
        print("No trades generated.")
        return

    trades_df = pd.DataFrame(all_trades)
    wins = trades_df[trades_df["pnl"] > 0]
    losses = trades_df[trades_df["pnl"] <= 0]

    total_pnl = trades_df["pnl"].sum()
    win_rate = len(wins) / len(trades_df) * 100

    print(f"  Total trades : {len(trades_df)}")
    print(f"  Wins         : {len(wins)}  |  Losses: {len(losses)}")
    print(f"  Win rate     : {win_rate:.1f}%")
    print(f"  Total PnL    : {total_pnl:+.2f}")
    print(f"  Avg win      : {wins['pnl'].mean():+.2f}" if len(wins) else "  Avg win      : N/A")
    print(f"  Avg loss     : {losses['pnl'].mean():+.2f}" if len(losses) else "  Avg loss     : N/A")
    print(f"  Best trade   : {trades_df['pnl'].max():+.2f}")
    print(f"  Worst trade  : {trades_df['pnl'].min():+.2f}")
    print("═" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backtest.py <path_to_1min_csv>")
        sys.exit(1)
    run_backtest(sys.argv[1])
