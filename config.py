# config.py — All backtest parameters in one place

# ── Data Mode ──────────────────────────────────────────────────────────────────
# "bs_sim"       : Black-Scholes simulation using VIX as IV proxy (no OM needed)
# "optionmetrics": Use real OptionMetrics historical options data
DATA_MODE = "bs_sim"

# ── Backtest Window ────────────────────────────────────────────────────────────
BACKTEST_START = "2018-01-01"
BACKTEST_END   = "2024-12-31"

# ── Underlying ─────────────────────────────────────────────────────────────────
UNDERLYING = "SPY"   # SPY for ETF-level, SPX for index options

# ── Options Parameters ─────────────────────────────────────────────────────────
DTE_TARGET       = 30    # Target days to expiry at entry
ROLL_DTE         = 7     # Roll position when DTE falls below this
PUT_STRIKE_PCT   = 0.95  # Long put strike as % of spot (0.95 = 5% OTM)
SHORT_STRIKE_PCT = 0.90  # Short put strike for spreads (0.90 = 10% OTM)
POSITION_SIZE    = 1     # Number of contracts per signal

# ── Risk-Free Rate ─────────────────────────────────────────────────────────────
RISK_FREE_RATE = 0.05    # Annual, used in BS pricing

# ── Regime Thresholds (MMS Dashboard) ─────────────────────────────────────────
VIX_THRESHOLDS = {
    "CALM":       (0,   15),
    "NORMAL":     (15,  25),
    "ELEVATED":   (25,  35),
    "STRESSED":   (35,  45),
    "CRISIS":     (45,  999),
}

MOVE_THRESHOLDS = {
    "NORMAL":     (0,   90),
    "ELEVATED":   (90,  120),
    "HIGH_STRESS":(120, 160),
    "CRISIS":     (160, 999),
}

COR1M_THRESHOLDS = {
    "CALM":       (0,   20),
    "ELEVATED":   (20,  40),
    "STRESSED":   (40,  60),
    "CRISIS":     (60,  999),
}

# ── Entry Signal ───────────────────────────────────────────────────────────────
# Hedge is opened when combined signal is one of these regimes
ENTRY_REGIMES = ["ELEVATED", "STRESSED", "CRISIS"]

# ── Reversion (Exit) Conditions — 6-of-6 MMS Dashboard Rules ──────────────────
REVERSION_VIX_LEVEL      = 25    # ① VIX < 25
REVERSION_MOVE_LEVEL     = 95    # ② MOVE < 95
REVERSION_COR1M_LEVEL    = 30    # ③ COR1M < 30
REVERSION_VIX_DOWN_DAYS  = 3     # ④ VIX down N+ consecutive days
# ⑤ Front spread in contango (VIX term structure check)
# ⑥ Breadth gate: SP500 > 50SMA ≥ 25 AND McClellan Oscillator > 0

REVERSION_CONDITIONS_REQUIRED = 6  # All 6 must pass for full exit signal

# ── Output Paths ───────────────────────────────────────────────────────────────
RESULTS_DIR     = "results/"
CHART_DPI       = 150
