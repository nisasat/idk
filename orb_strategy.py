"""
Opening Range Breakout (ORB) Strategy Engine

Logic
─────
1.  Identify the 09:35 EST candle → mark its HIGH and LOW (wicks included).
2.  Compute session VWAP and daily ATR for filtering.
3.  After the ORB candle closes, scan subsequent candles for a *strong* close
    above the ORB high (long) or below the ORB low (short).
4.  Apply filters:
        • VWAP directional bias  – price must be on the correct side of VWAP.
        • ATR range filter       – ORB range must sit within acceptable ATR bounds.
        • Premarket context      – session must have sufficient premarket volume.
5.  Generate a trade signal with entry, stop-loss, and take-profit levels.
"""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import pytz

import config
from indicators import compute_atr, compute_vwap
from premarket import analyse_premarket


@dataclass
class TradeSignal:
    direction: str          # "LONG" or "SHORT"
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: pd.Timestamp
    orb_high: float
    orb_low: float
    vwap_at_entry: float
    atr_value: float
    premarket: dict = field(default_factory=dict)

    def risk(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    def reward(self) -> float:
        return abs(self.take_profit - self.entry_price)

    def __str__(self) -> str:
        return (
            f"[{self.direction}] Entry={self.entry_price:.2f}  "
            f"Stop={self.stop_loss:.2f}  Target={self.take_profit:.2f}  "
            f"R:R=1:{self.reward() / self.risk():.1f}  "
            f"Time={self.entry_time}  VWAP={self.vwap_at_entry:.2f}  "
            f"ATR={self.atr_value:.2f}"
        )


class ORBStrategy:
    """Run the ORB strategy on a single day's intraday data."""

    def __init__(self, daily_atr: Optional[float] = None):
        self.daily_atr = daily_atr
        self.signals: list[TradeSignal] = []

    # ── public API ──────────────────────────────────────────────────────
    def run(self, day_df: pd.DataFrame) -> list[TradeSignal]:
        """
        Execute strategy on one trading day of 1-min bars.

        Parameters
        ----------
        day_df : pd.DataFrame
            Must have columns: open, high, low, close, volume.
            DatetimeIndex should be tz-aware US/Eastern (or UTC).

        Returns
        -------
        list[TradeSignal]
        """
        eastern = pytz.timezone(config.TIMEZONE)
        df = day_df.copy()

        # Ensure eastern tz
        if df.index.tz is None:
            df.index = df.index.tz_localize(eastern)
        else:
            df.index = df.index.tz_convert(eastern)

        # ── 1. Premarket context ────────────────────────────────────────
        pm = analyse_premarket(df)
        if not pm["pm_valid"]:
            return []

        # ── 2. Locate the 09:35 ORB candle ─────────────────────────────
        orb_candle = self._get_orb_candle(df)
        if orb_candle is None:
            return []

        orb_high = orb_candle["high"]
        orb_low = orb_candle["low"]
        orb_range = orb_high - orb_low

        if orb_range <= 0:
            return []

        # ── 3. ATR filter ───────────────────────────────────────────────
        atr_value = self._resolve_atr(df)
        if atr_value is None or atr_value <= 0:
            return []

        if orb_range < atr_value * config.ATR_MIN_MULTIPLIER:
            return []  # range too tight — likely noise
        if orb_range > atr_value * config.ATR_MAX_MULTIPLIER:
            return []  # range too wide — over-extended / gap

        # ── 4. Compute session VWAP ─────────────────────────────────────
        date_str = df.index[0].strftime("%Y-%m-%d")
        session_start = pd.Timestamp(
            f"{date_str} 09:30", tz=eastern
        )
        session_df = df.loc[df.index >= session_start].copy()
        session_df["vwap"] = compute_vwap(session_df)

        # ── 5. Scan for breakout candles after ORB close ────────────────
        entry_start = pd.Timestamp(
            f"{date_str} {config.TRADING_START}", tz=eastern
        )
        entry_end = pd.Timestamp(
            f"{date_str} {config.TRADING_END}", tz=eastern
        )
        candidates = session_df.loc[
            (session_df.index >= entry_start) & (session_df.index <= entry_end)
        ]

        trade_count = 0
        self.signals = []

        for ts, candle in candidates.iterrows():
            if trade_count >= config.MAX_TRADES_PER_DAY:
                break

            vwap_now = candle.get("vwap", None)
            if vwap_now is None:
                continue

            signal = self._evaluate_candle(
                ts, candle, orb_high, orb_low, vwap_now, atr_value, pm
            )
            if signal is not None:
                self.signals.append(signal)
                trade_count += 1

        return self.signals

    # ── internals ───────────────────────────────────────────────────────
    def _get_orb_candle(self, df: pd.DataFrame) -> Optional[pd.Series]:
        eastern = pytz.timezone(config.TIMEZONE)
        date_str = df.index[0].strftime("%Y-%m-%d")
        orb_ts = pd.Timestamp(f"{date_str} {config.ORB_CANDLE_TIME}", tz=eastern)

        if orb_ts in df.index:
            return df.loc[orb_ts]

        # Fuzzy match within a 1-minute window
        mask = (df.index >= orb_ts) & (
            df.index < orb_ts + pd.Timedelta(minutes=1)
        )
        orb_bars = df.loc[mask]
        if orb_bars.empty:
            return None
        return orb_bars.iloc[0]

    def _resolve_atr(self, df: pd.DataFrame) -> Optional[float]:
        if self.daily_atr is not None:
            return self.daily_atr

        # Compute intraday ATR from available bars as a fallback
        atr_series = compute_atr(df, period=config.ATR_PERIOD)
        last_valid = atr_series.dropna()
        if last_valid.empty:
            return None
        return last_valid.iloc[-1]

    def _evaluate_candle(
        self,
        ts: pd.Timestamp,
        candle: pd.Series,
        orb_high: float,
        orb_low: float,
        vwap: float,
        atr_value: float,
        pm: dict,
    ) -> Optional[TradeSignal]:
        """Check if *candle* is a strong breakout candle and return a signal."""

        body = abs(candle["close"] - candle["open"])
        total_range = candle["high"] - candle["low"]
        if total_range <= 0:
            return None

        body_ratio = body / total_range
        if body_ratio < config.MIN_BODY_RATIO:
            return None  # not a strong candle

        stop_buffer = config.STOP_LOSS_BUFFER_TICKS * config.TICK_SIZE

        # ── LONG breakout ───────────────────────────────────────────────
        if candle["close"] > orb_high and candle["open"] <= orb_high:
            # Bullish candle closed above ORB high
            if config.REQUIRE_VWAP_BIAS and vwap < orb_high:
                return None  # VWAP not confirming bullish bias

            entry = candle["close"]
            stop = orb_low - stop_buffer
            risk = entry - stop
            target = entry + (risk * config.RISK_REWARD_RATIO)

            return TradeSignal(
                direction="LONG",
                entry_price=entry,
                stop_loss=stop,
                take_profit=target,
                entry_time=ts,
                orb_high=orb_high,
                orb_low=orb_low,
                vwap_at_entry=vwap,
                atr_value=atr_value,
                premarket=pm,
            )

        # ── SHORT breakout ──────────────────────────────────────────────
        if candle["close"] < orb_low and candle["open"] >= orb_low:
            # Bearish candle closed below ORB low
            if config.REQUIRE_VWAP_BIAS and vwap > orb_low:
                return None  # VWAP not confirming bearish bias

            entry = candle["close"]
            stop = orb_high + stop_buffer
            risk = stop - entry
            target = entry - (risk * config.RISK_REWARD_RATIO)

            return TradeSignal(
                direction="SHORT",
                entry_price=entry,
                stop_loss=stop,
                take_profit=target,
                entry_time=ts,
                orb_high=orb_high,
                orb_low=orb_low,
                vwap_at_entry=vwap,
                atr_value=atr_value,
                premarket=pm,
            )

        return None
