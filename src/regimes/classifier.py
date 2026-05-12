"""
regimes/classifier.py

Classifies daily market conditions into VIX × MOVE × COR1M regimes
mirroring the MMS Vol Dashboard logic.
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
    vix, move, cor1m, vix_1d_chg, spx_above_50sma, mcclellan

    Returns df with added columns:
    vix_regime, move_regime, cor1m_regime, combined_signal,
    vix_down_consec, reversion_conditions_met, entry_signal, exit_signal
    """
    df = df.copy()

    df["vix_regime"]    = df["vix"].apply(classify_vix)
    df["move_regime"]   = df["move"].apply(classify_move)
    df["cor1m_regime"]  = df["cor1m"].apply(classify_cor1m)
    df["combined"]      = df.apply(
        lambda r: combined_signal(r["vix_regime"], r["move_regime"]), axis=1
    )

    # Consecutive VIX down days
    df["vix_down_consec"] = _rolling_consec_down(df["vix"])

    # 6-of-6 reversion checklist
    df["rv_vix"]      = df["vix"]           < REVERSION_VIX_LEVEL
    df["rv_move"]     = df["move"]          < REVERSION_MOVE_LEVEL
    df["rv_cor1m"]    = df["cor1m"]         < REVERSION_COR1M_LEVEL
    df["rv_vix_days"] = df["vix_down_consec"] >= REVERSION_VIX_DOWN_DAYS
    df["rv_contango"] = df.get("front_spread", pd.Series(0, index=df.index)) < 0
    df["rv_breadth"]  = (
        df.get("spx_above_50sma", pd.Series(0, index=df.index)) >= 25
    ) & (
        df.get("mcclellan", pd.Series(0, index=df.index)) > 0
    )

    reversion_cols = ["rv_vix", "rv_move", "rv_cor1m", "rv_vix_days", "rv_contango", "rv_breadth"]
    df["reversion_conditions_met"] = df[reversion_cols].sum(axis=1)
    df["reversion_watch"] = df["reversion_conditions_met"] >= REVERSION_CONDITIONS_REQUIRED

    # Entry: regime turns defensive
    defensive = {"REDUCE SIZING", "REDUCE / BUILD LIST", "HIGH STRESS",
                 "QUALITY ONLY", "MAX CASH", "CRISIS", "EXTREME CRISIS"}
    df["entry_signal"] = df["combined"].isin(defensive)

    # Exit: full reversion confirmed
    df["exit_signal"] = df["reversion_watch"]

    return df


def _rolling_consec_down(series: pd.Series) -> pd.Series:
    """Count consecutive days the series has declined."""
    result = []
    count = 0
    prev = None
    for val in series:
        if prev is not None and val < prev:
            count += 1
        else:
            count = 0
        result.append(count)
        prev = val
    return pd.Series(result, index=series.index)
