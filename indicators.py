"""
Technical indicators used by the ORB trading bot.
- VWAP  (anchored to session open)
- ATR   (Average True Range)
"""

import numpy as np
import pandas as pd


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Compute the Volume-Weighted Average Price from the start of the
    regular session (cumulative reset each day).

    Expects columns: high, low, close, volume  — with a DatetimeIndex.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    vwap = cum_tp_vol / cum_vol.replace(0, np.nan)
    return vwap


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Compute Average True Range over *period* bars.

    Expects columns: high, low, close — with a DatetimeIndex.
    """
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.rolling(window=period, min_periods=period).mean()
    return atr
