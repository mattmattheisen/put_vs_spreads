"""
regimes/classifier.py

Classifies daily market conditions into VIX × MOVE × COR1M regimes
mirroring the MMS Vol Dashboard logic.

TEMPORAL INTEGRITY NOTES
─────────────────────────────────────────────────────────────────────────────
RULE: Signals must be generated from fully *completed* prior bars.
      entry_signal and exit_signal on row[t] are derived from row[t-1]'s
      closes (via .shift(1)). The engine acts on them at row[t]'s open —
      which is the first realistic execution opportunity.

      BROKEN (original):  entry_signal[t] = f(vix[t])  → executed same day
      FIXED:              entry_signal[t] = f(vix[t-1]) → executed next open
─────────────────────────────────────────────────────────────────────────────
"""

import pandas as pd
import numpy as np
from config import (
    VIX_THRESHOLDS, MOVE_THRESHOLDS, COR1M_THRESHOLDS,
    REVERSION_VIX_LEVEL, REVERSION_MOVE_LEVEL, REVERSION_COR1M_LEVEL,
    REVERSION_VIX_DOWN_DAYS, REVERSION_CONDITIONS_REQUIRED,
)


def classify_vix(vix: float) -> str:
    for regime, (lo, hi) in VIX_THRESHOLDS.items():
        if lo <= vix < hi:
            return regime
    return "CRISIS"


def classify_move(move: float) -> str:
    for regime, (lo, hi) in MOVE_THRESHOLDS.items():
        if lo <= move < hi:
            return regime
    return "CRISIS"


def classify_cor1m(cor1m: float) -> str:
    for regime, (lo, hi) in COR1M_THRESHOLDS.items():
        if lo <= cor1m < hi:
            return regime
    return "CRISIS"


# Combined signal matrix — matches MMS Dashboard exactly
_COMBINED_MATRIX = {
    ("CALM",     "NORMAL"):      "FULL DEPLOYMENT",
    ("CALM",     "ELEVATED"):    "STANDARD OPS",
    ("CALM",     "HIGH_STRESS"): "REDUCE EQUITY",
    ("CALM",     "CRISIS"):      "CRISIS",
    ("NORMAL",   "NORMAL"):      "STANDARD OPS",
    ("NORMAL",   "ELEVATED"):    "STANDARD OPS",
    ("NORMAL",   "HIGH_STRESS"): "REDUCE SIZING",
    ("NORMAL",   "CRISIS"):      "HIGH STRESS",
    ("ELEVATED", "NORMAL"):      "REDUCE SIZING",
    ("ELEVATED", "ELEVATED"):    "REDUCE / BUILD LIST",
    ("ELEVATED", "HIGH_STRESS"): "HIGH STRESS",
    ("ELEVATED", "CRISIS"):      "CRISIS",
    ("STRESSED", "NORMAL"):      "QUALITY ONLY",
    ("STRESSED", "ELEVATED"):    "QUALITY ONLY",
    ("STRESSED", "HIGH_STRESS"): "MAX CASH",
    ("STRESSED", "CRISIS"):      "CRISIS",
    ("CRISIS",   "NORMAL"):      "MAX CASH",
    ("CRISIS",   "ELEVATED"):    "MAX CASH",
    ("CRISIS",   "HIGH_STRESS"): "MAX CASH",
    ("CRISIS",   "CRISIS"):      "EXTREME CRISIS",
}


def combined_signal(vix_regime: str, move_regime: str) -> str:
    return _COMBINED_MATRIX.get((vix_regime, move_regime), "UNKNOWN")


def classify_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add regime columns to a DataFrame with columns:
    vix, move, cor1m, front_spread (optional), spx_above_50sma (optional),
    mcclellan (optional).

    Returns df with added columns:
    vix_regime, move_regime, cor1m_regime, combined,
    vix_down_consec, reversion_conditions_met, reversion_watch,
    entry_signal, exit_signal

    TEMPORAL INTEGRITY
    ──────────────────
    All regime labels (vix_regime, move_regime, combined, etc.) are computed
    on the *current* row's closes — this is correct for informational purposes
    (the dashboard shows today's state).

    entry_signal and exit_signal are then .shift(1)-ed so that on any given
    row[t], the signal reflects *yesterday's* confirmed close state. The engine
    can then realistically execute at row[t]'s open without look-ahead bias.

    No threshold normalization or fitting occurs here — all thresholds are
    point-in-time constants from config, so no Rule 5 (normalization) risk.
    """
    df = df.copy()

    # ── Step 1: Classify each day's closes (informational — not yet tradeable)
    df["vix_regime"]   = df["vix"].apply(classify_vix)
    df["move_regime"]  = df["move"].apply(classify_move)
    df["cor1m_regime"] = df["cor1m"].apply(classify_cor1m)
    df["combined"]     = df.apply(
        lambda r: combined_signal(r["vix_regime"], r["move_regime"]), axis=1
    )

    # ── Step 2: Reversion checklist — based on current-bar closes
    #    (also informational; shifted before use as signals below)
    df["vix_down_consec"] = _rolling_consec_down(df["vix"])

    df["rv_vix"]      = df["vix"]              < REVERSION_VIX_LEVEL
    df["rv_move"]     = df["move"]             < REVERSION_MOVE_LEVEL
    df["rv_cor1m"]    = df["cor1m"]            < REVERSION_COR1M_LEVEL
    df["rv_vix_days"] = df["vix_down_consec"]  >= REVERSION_VIX_DOWN_DAYS
    df["rv_contango"] = df.get("front_spread",  pd.Series(0, index=df.index)) < 0
    df["rv_breadth"]  = (
        df.get("spx_above_50sma", pd.Series(0, index=df.index)) >= 25
    ) & (
        df.get("mcclellan",       pd.Series(0, index=df.index)) > 0
    )

    reversion_cols = ["rv_vix", "rv_move", "rv_cor1m", "rv_vix_days", "rv_contango", "rv_breadth"]
    df["reversion_conditions_met"] = df[reversion_cols].sum(axis=1)
    df["reversion_watch"]          = df["reversion_conditions_met"] >= REVERSION_CONDITIONS_REQUIRED

    # ── Step 3: Raw (same-bar) signals — NOT yet safe for execution
    defensive = {
        "REDUCE SIZING", "REDUCE / BUILD LIST", "HIGH STRESS",
        "QUALITY ONLY", "MAX CASH", "CRISIS", "EXTREME CRISIS",
    }
    _entry_raw = df["combined"].isin(defensive)
    _exit_raw  = df["reversion_watch"]

    # ── Step 4: TEMPORAL FIX — shift signals forward by 1 bar
    #    entry_signal[t] = _entry_raw[t-1]  → engine acts at open of bar t
    #    exit_signal[t]  = _exit_raw[t-1]   → engine acts at open of bar t
    #
    #    Row 0 has no prior bar → NaN → False (no phantom signal on day 1)
    df["entry_signal"] = _entry_raw.shift(1).fillna(False).astype(bool)
    df["exit_signal"]  = _exit_raw.shift(1).fillna(False).astype(bool)

    return df


def _rolling_consec_down(series: pd.Series) -> pd.Series:
    """Count consecutive days the series has declined (uses only prior values)."""
    result = []
    count  = 0
    prev   = None
    for val in series:
        if prev is not None and val < prev:
            count += 1
        else:
            count = 0
        result.append(count)
        prev = val
    return pd.Series(result, index=series.index)
