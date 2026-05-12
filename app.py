"""
app.py — Put vs. Spreads Dashboard
Regime-conditioned backtest: Long Puts vs. Put Spreads
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Put vs. Spreads — Regime Backtest",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Fidelity palette ──────────────────────────────────────────────────────────
FID_GREEN       = "#00843D"
FID_GREEN_LIGHT = "#5BAD7F"
FID_NAVY        = "#005EB8"
FID_CHARCOAL    = "#1A1A1A"
FID_GRAY_DARK   = "#4A4A4A"
FID_GRAY_MID    = "#767676"
FID_GRAY_LIGHT  = "#F4F4F4"
FID_RULE        = "#CCCCCC"
FID_WHITE       = "#FFFFFF"
FID_AMBER       = "#B8860B"
FID_RED         = "#C0392B"
FID_RED_DARK    = "#8B0000"

LP_COLOR  = FID_GREEN
PS_COLOR  = FID_NAVY

REGIME_COLORS = {
    "FULL DEPLOYMENT":    FID_GREEN,
    "STANDARD OPS":       FID_GREEN_LIGHT,
    "REDUCE SIZING":      FID_AMBER,
    "REDUCE / BUILD LIST":"#C8882A",
    "HIGH STRESS":        FID_RED,
    "QUALITY ONLY":       "#A93226",
    "MAX CASH":           FID_RED_DARK,
    "CRISIS":             "#6B0000",
    "EXTREME CRISIS":     "#4A0000",
    "UNKNOWN":            "#AAAAAA",
}

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {FID_CHARCOAL};
        border-right: 1px solid #2A2A2A;
    }}
    [data-testid="stSidebar"] * {{
        color: #E8E8E8 !important;
    }}
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stSlider label {{
        color: {FID_GRAY_MID} !important;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    /* Main background */
    .main .block-container {{
        background-color: {FID_WHITE};
        padding-top: 1.5rem;
        max-width: 1400px;
    }}

    /* Header bar */
    .header-bar {{
        background-color: {FID_GREEN};
        padding: 16px 28px;
        margin: -1.5rem -1rem 1.5rem -1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .header-title {{
        color: white;
        font-size: 18px;
        font-weight: 600;
        letter-spacing: -0.01em;
        margin: 0;
    }}
    .header-sub {{
        color: rgba(255,255,255,0.75);
        font-size: 12px;
        margin: 0;
        margin-top: 2px;
    }}

    /* Metric cards */
    .metric-card {{
        background: {FID_GRAY_LIGHT};
        border: 1px solid {FID_RULE};
        border-top: 3px solid {FID_GREEN};
        border-radius: 4px;
        padding: 16px 20px;
        height: 100%;
    }}
    .metric-card.navy {{
        border-top-color: {FID_NAVY};
    }}
    .metric-label {{
        font-size: 11px;
        color: {FID_GRAY_MID};
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 6px;
    }}
    .metric-value {{
        font-size: 26px;
        font-weight: 600;
        color: {FID_CHARCOAL};
        line-height: 1;
    }}
    .metric-delta {{
        font-size: 12px;
        color: {FID_GRAY_MID};
        margin-top: 4px;
    }}
    .metric-delta.positive {{ color: {FID_GREEN}; }}
    .metric-delta.negative {{ color: {FID_RED}; }}

    /* Section headers */
    .section-header {{
        font-size: 13px;
        font-weight: 600;
        color: {FID_CHARCOAL};
        text-transform: uppercase;
        letter-spacing: 0.08em;
        border-bottom: 2px solid {FID_GREEN};
        padding-bottom: 6px;
        margin-bottom: 16px;
        margin-top: 8px;
    }}

    /* Divider */
    hr {{
        border: none;
        border-top: 1px solid {FID_RULE};
        margin: 1.5rem 0;
    }}

    /* Hide streamlit chrome */
    #MainMenu, footer, header {{ visibility: hidden; }}
    .stDeployButton {{ display: none; }}
</style>
""", unsafe_allow_html=True)


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading market data...")
def load_data(start, end, dte, long_strike, short_strike):
    try:
        from src.backtester.engine import load_regime_data, run_backtest, trades_to_df
        from src.backtester.metrics import compute_metrics, compare_by_regime

        # Temporarily override config
        import config as cfg
        cfg.BACKTEST_START   = start
        cfg.BACKTEST_END     = end
        cfg.DTE_TARGET       = dte
        cfg.PUT_STRIKE_PCT   = long_strike
        cfg.SHORT_STRIKE_PCT = short_strike

        regime_df = load_regime_data()
        lp_trades, ps_trades = run_backtest(regime_df)
        lp_df = trades_to_df(lp_trades)
        ps_df = trades_to_df(ps_trades)

        return regime_df, lp_df, ps_df, None
    except Exception as e:
        return None, None, None, str(e)


def metric_card(label, value, delta=None, positive_good=True, navy=False):
    card_class = "metric-card navy" if navy else "metric-card"
    delta_html = ""
    if delta is not None:
        delta_class = "positive" if (positive_good and "+" in str(delta)) or \
                                    (not positive_good and "-" in str(delta)) else "negative"
        delta_html = f'<div class="metric-delta {delta_class}">{delta}</div>'
    return f"""
    <div class="{card_class}">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """


def plotly_layout(title="", height=400):
    return dict(
        title=dict(text=title, font=dict(size=13, color=FID_CHARCOAL, family="Inter"), x=0, xanchor="left"),
        height=height,
        paper_bgcolor=FID_WHITE,
        plot_bgcolor=FID_WHITE,
        font=dict(family="Inter", color=FID_CHARCOAL, size=11),
        xaxis=dict(showgrid=False, linecolor=FID_RULE, tickcolor=FID_RULE),
        yaxis=dict(gridcolor=FID_GRAY_LIGHT, linecolor=FID_RULE, tickcolor=FID_RULE),
        legend=dict(bgcolor=FID_WHITE, bordercolor=FID_RULE, borderwidth=1,
                    font=dict(size=11)),
        margin=dict(l=10, r=10, t=50, b=10),
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Parameters")
    st.markdown("---")

    start_date = st.selectbox("Backtest Start", ["2018-01-01", "2019-01-01", "2020-01-01"], index=0)
    end_date   = st.selectbox("Backtest End",   ["2024-12-31", "2023-12-31", "2022-12-31"], index=0)

    st.markdown("---")
    dte = st.slider("Days to Expiry (DTE)", 14, 60, 30, step=7)
    long_strike  = st.slider("Long Put Strike (%)", 85, 100, 95) / 100
    short_strike = st.slider("Short Put Strike (%)", 75, 95, 90) / 100

    st.markdown("---")
    st.markdown(f"""
    <div style="font-size:11px; color:#767676; line-height:1.6;">
        <div style="color:#5BAD7F; font-weight:600; margin-bottom:4px;">Data Mode</div>
        Black-Scholes simulation using VIX as IV proxy.<br><br>
        Switch to OptionMetrics in <code>config.py</code> for real fills.
    </div>
    """, unsafe_allow_html=True)

    run = st.button("Run Backtest", use_container_width=True,
                    type="primary")


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="header-bar">
    <div>
        <p class="header-title">Long Puts vs. Put Spreads</p>
        <p class="header-sub">Regime-Conditioned Backtest &nbsp;·&nbsp; VIX × MOVE × COR1M Signal Framework</p>
    </div>
    <div style="color:rgba(255,255,255,0.6); font-size:11px; text-align:right;">
        put_vs_spreads
    </div>
</div>
""", unsafe_allow_html=True)


# ── Run / load ────────────────────────────────────────────────────────────────
if "regime_df" not in st.session_state or run:
    with st.spinner("Running backtest..."):
        regime_df, lp_df, ps_df, err = load_data(
            start_date, end_date, dte, long_strike, short_strike
        )
    if err:
        st.error(f"Error: {err}")
        st.info("Make sure all dependencies are installed: `pip install -r requirements.txt`")
        st.stop()
    st.session_state.regime_df = regime_df
    st.session_state.lp_df     = lp_df
    st.session_state.ps_df     = ps_df

regime_df = st.session_state.regime_df
lp_df     = st.session_state.lp_df
ps_df     = st.session_state.ps_df

from src.backtester.metrics import compute_metrics, compare_by_regime
lp_m = compute_metrics(lp_df, "Long Put")
ps_m = compute_metrics(ps_df, "Put Spread")
premium_savings = (lp_m["total_premium"] - ps_m["total_premium"]) / lp_m["total_premium"] if lp_m["total_premium"] > 0 else 0
pnl_diff = lp_m["total_pnl"] - ps_m["total_pnl"]


# ── KPI Row ───────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Summary</div>', unsafe_allow_html=True)

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.markdown(metric_card("LP Total P&L",
        f"${lp_m['total_pnl']:,.0f}",
        f"+{lp_m['win_rate']:.0%} win rate"), unsafe_allow_html=True)
with c2:
    st.markdown(metric_card("PS Total P&L",
        f"${ps_m['total_pnl']:,.0f}",
        f"+{ps_m['win_rate']:.0%} win rate", navy=True), unsafe_allow_html=True)
with c3:
    st.markdown(metric_card("LP Premium Paid",
        f"${lp_m['total_premium']:,.0f}",
        "Total cost"), unsafe_allow_html=True)
with c4:
    st.markdown(metric_card("PS Premium Paid",
        f"${ps_m['total_premium']:,.0f}",
        f"{premium_savings:.0%} cheaper than LP", navy=True), unsafe_allow_html=True)
with c5:
    st.markdown(metric_card("LP Sharpe",
        f"{lp_m['sharpe']:.2f}",
        "Hedge leg only"), unsafe_allow_html=True)
with c6:
    st.markdown(metric_card("PS Sharpe",
        f"{ps_m['sharpe']:.2f}",
        "Hedge leg only", navy=True), unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)


# ── Regime Timeline ───────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Regime Timeline</div>', unsafe_allow_html=True)

fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                    row_heights=[0.4, 0.2, 0.2, 0.2],
                    vertical_spacing=0.03)

dates = pd.to_datetime(regime_df["date"])

# SPY with regime shading
fig.add_trace(go.Scatter(
    x=dates, y=regime_df["spot"],
    line=dict(color=FID_CHARCOAL, width=1.2),
    name="SPY", showlegend=True
), row=1, col=1)

for regime, color in REGIME_COLORS.items():
    mask = regime_df["combined"] == regime
    if mask.any():
        fig.add_trace(go.Scatter(
            x=dates, y=np.where(mask, regime_df["spot"], np.nan),
            fill="tozeroy", fillcolor=color + "22",
            line=dict(color="rgba(0,0,0,0)", width=0),
            name=regime, showlegend=False,
        ), row=1, col=1)

fig.add_trace(go.Scatter(x=dates, y=regime_df["vix"],
    line=dict(color=FID_CHARCOAL, width=1), name="VIX", showlegend=False), row=2, col=1)
fig.add_hline(y=25, line=dict(color=FID_GREEN, dash="dash", width=1), row=2, col=1)
fig.add_hline(y=35, line=dict(color=FID_RED, dash="dash", width=1), row=2, col=1)

fig.add_trace(go.Scatter(x=dates, y=regime_df["move"],
    line=dict(color=FID_GRAY_DARK, width=1), name="MOVE", showlegend=False), row=3, col=1)
fig.add_hline(y=90,  line=dict(color=FID_GREEN, dash="dash", width=1), row=3, col=1)
fig.add_hline(y=120, line=dict(color=FID_RED, dash="dash", width=1), row=3, col=1)

fig.add_trace(go.Scatter(x=dates, y=regime_df["cor1m"],
    line=dict(color=FID_GRAY_MID, width=1), name="COR1M", showlegend=False), row=4, col=1)
fig.add_hline(y=40, line=dict(color=FID_RED, dash="dash", width=1), row=4, col=1)

fig.update_layout(**plotly_layout(height=520))
fig.update_yaxes(gridcolor=FID_GRAY_LIGHT, linecolor=FID_RULE)
fig.update_xaxes(showgrid=False, linecolor=FID_RULE)
fig.update_yaxes(title_text="SPY", row=1, col=1)
fig.update_yaxes(title_text="VIX", row=2, col=1)
fig.update_yaxes(title_text="MOVE", row=3, col=1)
fig.update_yaxes(title_text="COR1M", row=4, col=1)

st.plotly_chart(fig, use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)


# ── Cumulative P&L ────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Cumulative P&L</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    lp_cum = lp_df.set_index("close_date")["pnl"].sort_index().cumsum()
    ps_cum = ps_df.set_index("close_date")["pnl"].sort_index().cumsum()

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=pd.to_datetime(lp_cum.index), y=lp_cum.values,
        line=dict(color=LP_COLOR, width=2), name="Long Put"))
    fig2.add_trace(go.Scatter(x=pd.to_datetime(ps_cum.index), y=ps_cum.values,
        line=dict(color=PS_COLOR, width=2), name="Put Spread"))
    fig2.add_hline(y=0, line=dict(color=FID_RULE, width=1))
    fig2.update_layout(**plotly_layout("Cumulative P&L (net of premium)", height=340))
    fig2.update_yaxes(tickprefix="$", tickformat=",.0f")
    st.plotly_chart(fig2, use_container_width=True)

with col2:
    lp_prem = lp_df.set_index("close_date")["premium_paid"].sort_index().cumsum()
    ps_prem = ps_df.set_index("close_date")["premium_paid"].sort_index().cumsum()

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=pd.to_datetime(lp_prem.index), y=lp_prem.values,
        line=dict(color=LP_COLOR, width=2), name="Long Put"))
    fig3.add_trace(go.Scatter(x=pd.to_datetime(ps_prem.index), y=ps_prem.values,
        line=dict(color=PS_COLOR, width=2), name="Put Spread"))
    fig3.update_layout(**plotly_layout("Cumulative Premium Paid", height=340))
    fig3.update_yaxes(tickprefix="$", tickformat=",.0f")
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)


# ── Regime Breakdown ──────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Performance by Regime</div>', unsafe_allow_html=True)

regime_compare = compare_by_regime(lp_df, ps_df)
regimes = regime_compare.index.tolist()

col1, col2 = st.columns(2)

with col1:
    lp_pnl = regime_compare.get("lp_avg_pnl", pd.Series(0, index=regimes)).fillna(0)
    ps_pnl = regime_compare.get("ps_avg_pnl", pd.Series(0, index=regimes)).fillna(0)

    fig4 = go.Figure()
    fig4.add_trace(go.Bar(x=regimes, y=lp_pnl, name="Long Put",
        marker_color=LP_COLOR, opacity=0.9))
    fig4.add_trace(go.Bar(x=regimes, y=ps_pnl, name="Put Spread",
        marker_color=PS_COLOR, opacity=0.9))
    fig4.add_hline(y=0, line=dict(color=FID_RULE, width=1))
    fig4.update_layout(**plotly_layout("Avg P&L per Trade by Regime", height=340),
                       barmode="group")
    fig4.update_yaxes(tickprefix="$", tickformat=",.0f")
    fig4.update_xaxes(tickangle=-30)
    st.plotly_chart(fig4, use_container_width=True)

with col2:
    lp_rop = regime_compare.get("lp_avg_rop", pd.Series(0, index=regimes)).fillna(0) * 100
    ps_rop = regime_compare.get("ps_avg_rop", pd.Series(0, index=regimes)).fillna(0) * 100

    fig5 = go.Figure()
    fig5.add_trace(go.Bar(x=regimes, y=lp_rop, name="Long Put",
        marker_color=LP_COLOR, opacity=0.9))
    fig5.add_trace(go.Bar(x=regimes, y=ps_rop, name="Put Spread",
        marker_color=PS_COLOR, opacity=0.9))
    fig5.add_hline(y=0, line=dict(color=FID_RULE, width=1))
    fig5.update_layout(**plotly_layout("Return on Premium by Regime (%)", height=340),
                       barmode="group")
    fig5.update_yaxes(ticksuffix="%")
    fig5.update_xaxes(tickangle=-30)
    st.plotly_chart(fig5, use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)


# ── Cap Breach ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Spread Cap Breach — When the Short Strike Binds</div>',
            unsafe_allow_html=True)

ps_analysis = ps_df.copy()
ps_analysis["spot_decline_pct"] = (
    (ps_analysis["open_spot"] - ps_analysis["close_spot"]) / ps_analysis["open_spot"]
)
threshold = 1 - short_strike
ps_analysis["cap_hit"] = ps_analysis["spot_decline_pct"] > threshold

cap_by_regime = ps_analysis.groupby("regime")["cap_hit"].agg(["sum","count","mean"])
cap_by_regime.columns = ["cap_hits", "total_trades", "cap_hit_rate"]
cap_rates = (cap_by_regime["cap_hit_rate"] * 100).tolist()
cap_regimes = cap_by_regime.index.tolist()

bar_colors = [FID_RED if r > 20 else FID_AMBER if r > 10 else FID_GREEN for r in cap_rates]

fig6 = go.Figure()
fig6.add_trace(go.Bar(
    x=cap_regimes, y=cap_rates,
    marker_color=bar_colors, opacity=0.9,
    text=[f"{r:.1f}%" for r in cap_rates],
    textposition="outside",
    textfont=dict(size=11, color=FID_CHARCOAL),
))
fig6.update_layout(
    **plotly_layout(f"Cap Breach Rate by Regime  (SPY decline > {threshold:.0%})", height=360),
    showlegend=False
)
fig6.update_yaxes(ticksuffix="%")
fig6.update_xaxes(tickangle=-30)
st.plotly_chart(fig6, use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)


# ── Trade Table ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Trade Log</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Long Put", "Put Spread"])

display_cols = ["open_date", "close_date", "regime", "open_spot",
                "close_spot", "premium_paid", "pnl", "close_reason"]

with tab1:
    show = lp_df[[c for c in display_cols if c in lp_df.columns]].copy()
    show["pnl"] = show["pnl"].map("${:,.0f}".format)
    show["premium_paid"] = show["premium_paid"].map("${:,.0f}".format)
    st.dataframe(show, use_container_width=True, height=280)

with tab2:
    show = ps_df[[c for c in display_cols if c in ps_df.columns]].copy()
    show["pnl"] = show["pnl"].map("${:,.0f}".format)
    show["premium_paid"] = show["premium_paid"].map("${:,.0f}".format)
    st.dataframe(show, use_container_width=True, height=280)
