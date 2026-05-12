"""
backtester/metrics.py

Performance analytics for comparing Long Put vs. Put Spread by regime.
"""

import pandas as pd
import numpy as np
from typing import Optional


def compute_metrics(df: pd.DataFrame, label: str = "") -> dict:
    """
    Compute full performance metrics from a trades DataFrame.

    Required columns: pnl, premium_paid, regime, open_date, close_date,
                      spot_move_pct (or open_spot/close_spot)
    """
    if df.empty:
        return {"label": label, "n_trades": 0}

    total_pnl      = df["pnl"].sum()
    total_premium  = df["premium_paid"].sum()
    win_rate       = (df["pnl"] > 0).mean()
    avg_pnl        = df["pnl"].mean()
    avg_premium    = df["premium_paid"].mean()
    rop            = df["pnl"] / df["premium_paid"].replace(0, np.nan)  # return on premium
    avg_rop        = rop.mean()

    # Sharpe of hedge leg (daily pnl / std)
    sharpe = (df["pnl"].mean() / df["pnl"].std()) * np.sqrt(252 / 30) if df["pnl"].std() > 0 else 0

    # Breakeven move required
    if "open_spot" in df.columns and "premium_paid" in df.columns:
        df = df.copy()
        df["_be_move"] = -df["premium_paid"] / (df["open_spot"] * 100)  # approximate
        avg_be_move = df["_be_move"].mean()
    else:
        avg_be_move = np.nan

    metrics = {
        "label":           label,
        "n_trades":        len(df),
        "total_pnl":       total_pnl,
        "total_premium":   total_premium,
        "net_pnl":         total_pnl,         # pnl already net of premium in strategies
        "win_rate":        win_rate,
        "avg_pnl":         avg_pnl,
        "avg_premium":     avg_premium,
        "avg_rop":         avg_rop,            # average return on premium
        "sharpe":          sharpe,
        "avg_be_move_pct": avg_be_move,
        "best_trade":      df["pnl"].max(),
        "worst_trade":     df["pnl"].min(),
    }
    return metrics


def compute_by_regime(df: pd.DataFrame, label: str = "") -> pd.DataFrame:
    """Break down metrics by VIX regime."""
    if df.empty:
        return pd.DataFrame()

    rows = []
    for regime, grp in df.groupby("regime"):
        m = compute_metrics(grp, label=f"{label}|{regime}")
        m["regime"] = regime
        rows.append(m)

    result = pd.DataFrame(rows).set_index("regime")
    return result


def compare_strategies(lp_df: pd.DataFrame, ps_df: pd.DataFrame) -> pd.DataFrame:
    """
    Side-by-side comparison of Long Put vs. Put Spread.
    Returns a summary DataFrame suitable for display.
    """
    lp_m = compute_metrics(lp_df, "Long Put")
    ps_m = compute_metrics(ps_df, "Put Spread")

    comparison = pd.DataFrame([lp_m, ps_m]).set_index("label")
    return comparison


def compare_by_regime(lp_df: pd.DataFrame, ps_df: pd.DataFrame) -> pd.DataFrame:
    """
    Regime-bucketed comparison. Useful for the Gambit regime analysis.
    """
    lp_regime = compute_by_regime(lp_df, "Long Put")
    ps_regime = compute_by_regime(ps_df, "Put Spread")

    lp_regime.columns = [f"lp_{c}" for c in lp_regime.columns]
    ps_regime.columns = [f"ps_{c}" for c in ps_regime.columns]

    return pd.concat([lp_regime, ps_regime], axis=1)


def tail_capture_efficiency(trades_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each trade, compute: pnl / (spot decline * notional).
    Measures how efficiently the hedge captured the drawdown.
    """
    df = trades_df.copy()
    df["spot_decline"] = (df["open_spot"] - df["close_spot"]).clip(lower=0)
    df["notional"]     = df["open_spot"] * df["contracts"] * 100
    df["tail_capture"] = np.where(
        df["spot_decline"] > 0,
        df["pnl"] / (df["spot_decline"] * df["contracts"] * 100),
        np.nan,
    )
    return df[["open_date", "regime", "spot_decline", "pnl", "tail_capture"]]


def print_summary(df: pd.DataFrame):
    m = compute_metrics(df)
    print(f"  Trades:          {m['n_trades']}")
    print(f"  Total P&L:      ${m['total_pnl']:,.0f}")
    print(f"  Total Premium:  ${m['total_premium']:,.0f}")
    print(f"  Win Rate:        {m['win_rate']:.1%}")
    print(f"  Avg P&L/Trade:  ${m['avg_pnl']:,.0f}")
    print(f"  Avg Premium:    ${m['avg_premium']:,.0f}")
    print(f"  Avg ROP:         {m['avg_rop']:.1%}")
    print(f"  Sharpe:          {m['sharpe']:.2f}")
