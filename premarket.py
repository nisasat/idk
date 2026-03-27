"""
Pre-market context analysis.

Provides directional bias and volume context from the pre-market session
(04:00 – 09:30 EST) to filter ORB setups.
"""

import pandas as pd
import pytz

import config


def analyse_premarket(day_df: pd.DataFrame) -> dict:
    """
    Analyse the pre-market window for a single trading day.

    Parameters
    ----------
    day_df : pd.DataFrame
        Intraday bars for one calendar day. Index must be tz-aware
        datetime in US/Eastern (or will be converted).

    Returns
    -------
    dict with keys:
        pm_high        – highest price during pre-market
        pm_low         – lowest price during pre-market
        pm_volume      – total volume during pre-market
        pm_direction   – 'bullish' | 'bearish' | 'neutral'
        pm_valid       – True if volume exceeds threshold
    """
    eastern = pytz.timezone(config.TIMEZONE)
    idx = day_df.index
    if idx.tz is None:
        idx = idx.tz_localize(eastern)
    else:
        idx = idx.tz_convert(eastern)

    date_str = idx[0].strftime("%Y-%m-%d")
    pm_start = pd.Timestamp(f"{date_str} {config.PREMARKET_START}", tz=eastern)
    pm_end = pd.Timestamp(f"{date_str} {config.PREMARKET_END}", tz=eastern)

    pm_bars = day_df.loc[(idx >= pm_start) & (idx < pm_end)]

    if pm_bars.empty:
        return {
            "pm_high": None,
            "pm_low": None,
            "pm_volume": 0,
            "pm_direction": "neutral",
            "pm_valid": False,
        }

    pm_high = pm_bars["high"].max()
    pm_low = pm_bars["low"].min()
    pm_volume = pm_bars["volume"].sum()
    pm_open = pm_bars["open"].iloc[0]
    pm_close = pm_bars["close"].iloc[-1]

    if pm_close > pm_open:
        pm_direction = "bullish"
    elif pm_close < pm_open:
        pm_direction = "bearish"
    else:
        pm_direction = "neutral"

    return {
        "pm_high": pm_high,
        "pm_low": pm_low,
        "pm_volume": pm_volume,
        "pm_direction": pm_direction,
        "pm_valid": pm_volume >= config.PREMARKET_VOLUME_THRESHOLD,
    }
