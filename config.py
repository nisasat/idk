"""
ORB Trading Bot Configuration
"""

# ── Timing ──────────────────────────────────────────────────────────────────
ORB_CANDLE_TIME = "09:35"           # The single candle that defines the Opening Range
PREMARKET_START = "04:00"           # Pre-market window start (EST)
PREMARKET_END = "09:30"             # Pre-market window end (EST)
TRADING_START = "09:36"             # Earliest entry (after ORB candle closes)
TRADING_END = "15:45"               # Last allowed entry time (EST)
TIMEZONE = "US/Eastern"

# ── Candle Settings ─────────────────────────────────────────────────────────
CANDLE_INTERVAL = "1min"            # 1-minute candles for precision

# ── ORB Breakout Confirmation ───────────────────────────────────────────────
# A "strong candle" must close beyond the ORB level AND have a body that is
# at least this fraction of its total range (wick-to-wick).
MIN_BODY_RATIO = 0.50               # body >= 50 % of total candle range

# ── VWAP Directional Bias ──────────────────────────────────────────────────
# Long entries require price AND VWAP confirmation above ORB high.
# Short entries require price AND VWAP confirmation below ORB low.
REQUIRE_VWAP_BIAS = True

# ── ATR Filter ──────────────────────────────────────────────────────────────
ATR_PERIOD = 14                     # Look-back for Average True Range
ATR_MIN_MULTIPLIER = 0.5            # ORB range must be >= ATR * this value
ATR_MAX_MULTIPLIER = 2.0            # ORB range must be <= ATR * this value
# Filters out days where the ORB range is abnormally small (noise) or
# abnormally large (over-extended / gap day).

# ── Risk Management ────────────────────────────────────────────────────────
STOP_LOSS_BUFFER_TICKS = 2          # Extra ticks beyond ORB level for stop
TICK_SIZE = 0.25                    # ES futures tick size (adjust per instrument)
RISK_REWARD_RATIO = 2.0             # Target = entry + RR * |entry - stop|
MAX_TRADES_PER_DAY = 2              # Cap daily attempts

# ── Premarket Context ──────────────────────────────────────────────────────
PREMARKET_VOLUME_THRESHOLD = 1000   # Min premarket volume to consider the day valid
