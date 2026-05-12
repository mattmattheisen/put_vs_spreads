"""
app.py — Put vs. Spreads Dashboard
Regime-conditioned backtest: Long Puts vs. Put Spreads
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Put vs. Spreads — Regime Backtest",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Palette ───────────────────────────────────────────────────────────────────
FID_GREEN       = "#00843D"
FID_GREEN_LIGHT = "#5BAD7F"
FID_NAVY        = "#005EB8"
FID_CHARCOAL    = "#1A1A1A"
FID_GRAY_DARK   = "#4A4A4A"
FID_GRAY_MID    = "#767676"
FID_GRAY_LIGHT  = "#F4F4F4"
FID_RULE        = "#DDDDDD"
FID_WHITE       = "#FFFFFF"
FID_AMBER       = "#B8860B"
FID_RED         = "#C0392B"
FID_RED_DARK    = "#8B0000"

LP_COLOR = FID_GREEN
PS_COLOR = FID_NAVY

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

# ── Default parameters (hardcoded — no sliders) ───────────────────────────────
BACKTEST_START  = "2018-01-01"
BACKTEST_END    = "2024-12-31"
DTE             = 30
LONG_STRIKE     = 0.95
SHORT_STRIKE    = 0.90

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
        background-color: {FID_WHITE};
    }}

    /* Hide sidebar toggle and streamlit chrome */
    [data-testid="collapsedControl"] {{ display: none; }}
    #MainMenu, footer, header {{ visibility: hidden; }}
    .stDeployButton {{ display: none; }}

    /* Remove default padding */
    .main .block-container {{
        padding: 0 2rem 2rem 2rem;
        max-width: 100%;
    }}

    /* Header */
    .top-header {{
        background-color: {FID_GREEN};
        padding: 18px 32px;
        margin: 0 -2rem 2rem -2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 3px solid #006830;
    }}
    .top-header-left h1 {{
        color: white;
        font-size: 20px;
        font-weight: 600;
        margin: 0;
        letter-spacing: -0.02em;
    }}
    .top-header-left p {{
        color: rgba(255,255,255,0.72);
        font-size: 12px;
        margin: 3px 0 0 0;
        letter-spacing: 0.01em;
    }}
    .top-header-right {{
        text-align: right;
        color: rgba(255,255,255,0.55);
        font-size: 11px;
        font-family: 'Courier New', monospace;
    }}

    /* Param strip */
    .param-strip {{
        background: {FID_GRAY_LIGHT};
        border: 1px solid {FID_RULE};
        border-radius: 4px;
        padding: 12px 24px;
        margin-bottom: 24px;
        display: flex;
        gap: 40px;
        align-items: center;
    }}
    .param-item {{
        display: flex;
        flex-direction: column;
    }}
    .param-label {{
        font-size: 10px;
        color: {FID_GRAY_MID};
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin-bottom: 2px;
    }}
    .param-value {{
        font-size: 14px;
        font-weight: 600;
        color: {FID_CHARCOAL};
    }}

    /* KPI cards */
    .kpi-row {{
        display: flex;
        gap: 16px;
        margin-bottom: 28px;
    }}
    .kpi-card {{
        flex: 1;
        background: {FID_WHITE};
        border: 1px solid {FID_RULE};
        border-top: 3px solid {FID_GREEN};
        border-radius: 3px;
        padding: 18px 20px;
    }}
    .kpi-card.navy {{ border-top-color: {FID_NAVY}; }}
    .kpi-card.amber {{ border-top-color: {FID_AMBER}; }}
    .kpi-label {{
        font-size: 10px;
        color: {FID_GRAY_MID};
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin-bottom: 8px;
    }}
    .kpi-value {{
        font-size: 28px;
        font-weight: 700;
        color: {FID_CHARCOAL};
        line-height: 1;
        letter-spacing: -0.02em;
    }}
    .kpi-sub {{
        font-size: 11px;
        color: {FID_GRAY_MID};
        margin-top: 5px;
    }}
    .kpi-sub.green {{ color: {FID_GREEN}; font-weight: 500; }}
    .kpi-sub.navy  {{ color: {FID_NAVY};  font-weight: 500; }}

    /* Section labels */
    .section-label {{
        font-size: 11px;
        font-weight: 700;
        color: {FID_GRAY_MID};
        text-transform: uppercase;
        letter-spacing: 0.10em;
        border-bottom: 1px solid {FID_RULE};
        padding-bottom: 8px;
        margin-bottom: 16px;
        margin-top: 4px;
    }}

    /* Divider */
    .divider {{
        border: none;
        border-top: 1px solid {FID_RULE};
        margin: 28px 0;
    }}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def plotly_base(title="", height=400):
    return dict(
        title=dict(text=title, font=dict(size=12, color=FID_CHARCOAL, family="Inter"),
                   x=0, xanchor="left", y=0.97),
        height=height,
        paper_bgcolor=FID_WHITE,
        plot_bgcolor=FID_WHITE,
        font=dict(family="Inter", color=FID_CHARCOAL, size=11),
        xaxis=dict(showgrid=False, linecolor=FID_RULE, tickcolor=FID_RULE, zeroline=False),
        yaxis=dict(gridcolor=FID_GRAY_LIGHT, linecolor=FID_RULE, tickcolor=FID_RULE, zeroline=False),
        legend=dict(bgcolor=FID_WHITE, bordercolor=FID_RULE, borderwidth=1,
                    orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=8, r=8, t=48, b=8),
    )


def kpi(label, value, sub="", accent="green"):
    return f"""
    <div class="kpi-card {'navy' if accent=='navy' else 'amber' if accent=='amber' else ''}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub {accent}">{sub}</div>
    </div>"""


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="top-header">
    <div class="top-header-left">
        <h1>Long Puts vs. Put Spreads</h1>
        <p>Regime-Conditioned Backtest &nbsp;·&nbsp; VIX &times; MOVE &times; COR1M Signal Framework</p>
    </div>
    <div class="top-header-right" style="display:flex; align-items:center; gap:14px;">
        <div style="text-align:right;">
            <div style="color:white; font-size:14px; font-weight:600; letter-spacing:0.02em;">Shomer Analytics</div>
            <div style="color:rgba(255,255,255,0.55); font-size:11px; font-family:'Courier New',monospace; margin-top:2px;">put_vs_spreads &nbsp;·&nbsp; {BACKTEST_START} &rarr; {BACKTEST_END}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Running backtest...")
def load_all():
    from src.backtester.engine import load_regime_data, run_backtest, trades_to_df
    import config as cfg
    cfg.BACKTEST_START   = BACKTEST_START
    cfg.BACKTEST_END     = BACKTEST_END
    cfg.DTE_TARGET       = DTE
    cfg.PUT_STRIKE_PCT   = LONG_STRIKE
    cfg.SHORT_STRIKE_PCT = SHORT_STRIKE

    regime_df = load_regime_data()
    lp_trades, ps_trades = run_backtest(regime_df)
    lp_df = trades_to_df(lp_trades)
    ps_df = trades_to_df(ps_trades)
    return regime_df, lp_df, ps_df

try:
    regime_df, lp_df, ps_df = load_all()
except Exception as e:
    st.error(f"Backtest error: {e}")
    st.stop()


# ── Metrics ───────────────────────────────────────────────────────────────────
from src.backtester.metrics import compute_metrics, compare_by_regime

lp_m = compute_metrics(lp_df, "Long Put")
ps_m = compute_metrics(ps_df, "Put Spread")
premium_savings = (
    (lp_m["total_premium"] - ps_m["total_premium"]) / lp_m["total_premium"]
    if lp_m.get("total_premium", 0) > 0 else 0
)


# ── Param strip ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="param-strip">
    <div class="param-item">
        <span class="param-label">Period</span>
        <span class="param-value">{BACKTEST_START} &rarr; {BACKTEST_END}</span>
    </div>
    <div class="param-item">
        <span class="param-label">Underlying</span>
        <span class="param-value">SPY</span>
    </div>
    <div class="param-item">
        <span class="param-label">DTE Target</span>
        <span class="param-value">{DTE} days</span>
    </div>
    <div class="param-item">
        <span class="param-label">Long Put Strike</span>
        <span class="param-value">{LONG_STRIKE:.0%} of spot</span>
    </div>
    <div class="param-item">
        <span class="param-label">Short Put Strike</span>
        <span class="param-value">{SHORT_STRIKE:.0%} of spot</span>
    </div>
    <div class="param-item">
        <span class="param-label">Data Mode</span>
        <span class="param-value">Black-Scholes / VIX</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ── KPI Row ───────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Summary</div>', unsafe_allow_html=True)

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.markdown(kpi("LP Total P&L",
        f"${lp_m['total_pnl']:,.0f}",
        f"{lp_m['win_rate']:.0%} win rate"), unsafe_allow_html=True)
with c2:
    st.markdown(kpi("PS Total P&L",
        f"${ps_m['total_pnl']:,.0f}",
        f"{ps_m['win_rate']:.0%} win rate", "navy"), unsafe_allow_html=True)
with c3:
    st.markdown(kpi("LP Premium Paid",
        f"${lp_m['total_premium']:,.0f}",
        f"Avg ${lp_m['avg_premium']:,.0f}/trade"), unsafe_allow_html=True)
with c4:
    st.markdown(kpi("PS Premium Paid",
        f"${ps_m['total_premium']:,.0f}",
        f"{premium_savings:.0%} cheaper than LP", "navy"), unsafe_allow_html=True)
with c5:
    st.markdown(kpi("LP Sharpe",
        f"{lp_m['sharpe']:.2f}",
        "Hedge leg"), unsafe_allow_html=True)
with c6:
    st.markdown(kpi("PS Sharpe",
        f"{ps_m['sharpe']:.2f}",
        "Hedge leg", "navy"), unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


# ── Regime Timeline ───────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Regime Timeline</div>', unsafe_allow_html=True)

dates = pd.to_datetime(regime_df["date"])

fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                    row_heights=[0.42, 0.19, 0.19, 0.19],
                    vertical_spacing=0.025)

fig.add_trace(go.Scatter(
    x=dates, y=regime_df["spot"],
    line=dict(color=FID_CHARCOAL, width=1.3),
    name="SPY"
), row=1, col=1)

for regime, color in REGIME_COLORS.items():
    mask = regime_df["combined"] == regime
    if mask.any():
        fig.add_trace(go.Scatter(
            x=dates,
            y=np.where(mask, regime_df["spot"].max() * 1.05, np.nan),
            fill="tozeroy",
            fillcolor=color + "1A",
            line=dict(color="rgba(0,0,0,0)", width=0),
            name=regime, showlegend=False,
        ), row=1, col=1)

fig.add_trace(go.Scatter(x=dates, y=regime_df["vix"],
    line=dict(color="#333333", width=0.9), name="VIX", showlegend=False), row=2, col=1)
fig.add_hline(y=25, line=dict(color=FID_GREEN, dash="dot", width=1), row=2, col=1)
fig.add_hline(y=35, line=dict(color=FID_RED,   dash="dot", width=1), row=2, col=1)

fig.add_trace(go.Scatter(x=dates, y=regime_df["move"],
    line=dict(color="#555555", width=0.9), name="MOVE", showlegend=False), row=3, col=1)
fig.add_hline(y=90,  line=dict(color=FID_GREEN, dash="dot", width=1), row=3, col=1)
fig.add_hline(y=120, line=dict(color=FID_RED,   dash="dot", width=1), row=3, col=1)

fig.add_trace(go.Scatter(x=dates, y=regime_df["cor1m"],
    line=dict(color="#777777", width=0.9), name="COR1M", showlegend=False), row=4, col=1)
fig.add_hline(y=40, line=dict(color=FID_RED, dash="dot", width=1), row=4, col=1)

fig.update_layout(**plotly_base(height=500))
for r, label in [(1,"SPY"),(2,"VIX"),(3,"MOVE"),(4,"COR1M")]:
    fig.update_yaxes(title_text=label, title_font=dict(size=10), gridcolor=FID_GRAY_LIGHT,
                     linecolor=FID_RULE, row=r, col=1)
fig.update_xaxes(showgrid=False, linecolor=FID_RULE)

st.plotly_chart(fig, use_container_width=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


# ── Cumulative P&L ────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Cumulative P&L</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    lp_cum = lp_df.set_index("close_date")["pnl"].sort_index().cumsum()
    ps_cum = ps_df.set_index("close_date")["pnl"].sort_index().cumsum()
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=pd.to_datetime(lp_cum.index), y=lp_cum.values,
        line=dict(color=LP_COLOR, width=2), name="Long Put", fill="tozeroy",
        fillcolor=LP_COLOR + "0D"))
    fig2.add_trace(go.Scatter(x=pd.to_datetime(ps_cum.index), y=ps_cum.values,
        line=dict(color=PS_COLOR, width=2), name="Put Spread"))
    fig2.add_hline(y=0, line=dict(color=FID_RULE, width=0.8))
    fig2.update_layout(**plotly_base("Cumulative P&L — Net of Premium", height=320))
    fig2.update_yaxes(tickprefix="$", tickformat=",.0f")
    st.plotly_chart(fig2, use_container_width=True)

with col2:
    lp_prem = lp_df.set_index("close_date")["premium_paid"].sort_index().cumsum()
    ps_prem = ps_df.set_index("close_date")["premium_paid"].sort_index().cumsum()
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=pd.to_datetime(lp_prem.index), y=lp_prem.values,
        line=dict(color=LP_COLOR, width=2), name="Long Put"))
    fig3.add_trace(go.Scatter(x=pd.to_datetime(ps_prem.index), y=ps_prem.values,
        line=dict(color=PS_COLOR, width=2), name="Put Spread", fill="tonexty",
        fillcolor=PS_COLOR + "0D"))
    fig3.update_layout(**plotly_base("Cumulative Premium Paid — Cost Drag", height=320))
    fig3.update_yaxes(tickprefix="$", tickformat=",.0f")
    st.plotly_chart(fig3, use_container_width=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


# ── Regime Breakdown ──────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Performance by Regime</div>', unsafe_allow_html=True)

regime_compare = compare_by_regime(lp_df, ps_df)
regimes = regime_compare.index.tolist()

col1, col2 = st.columns(2)

with col1:
    lp_pnl = [float(v) for v in regime_compare.get("lp_avg_pnl", pd.Series(0, index=regimes)).fillna(0)]
    ps_pnl = [float(v) for v in regime_compare.get("ps_avg_pnl", pd.Series(0, index=regimes)).fillna(0)]
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(x=regimes, y=lp_pnl, name="Long Put",
        marker_color=LP_COLOR, opacity=0.9, marker_line_width=0))
    fig4.add_trace(go.Bar(x=regimes, y=ps_pnl, name="Put Spread",
        marker_color=PS_COLOR, opacity=0.9, marker_line_width=0))
    fig4.add_hline(y=0, line=dict(color=FID_RULE, width=0.8))
    fig4.update_layout(**plotly_base("Avg P&L per Trade by Regime", height=320), barmode="group")
    fig4.update_yaxes(tickprefix="$", tickformat=",.0f")
    fig4.update_xaxes(tickangle=-30, tickfont=dict(size=9))
    st.plotly_chart(fig4, use_container_width=True)

with col2:
    lp_rop = [float(v)*100 for v in regime_compare.get("lp_avg_rop", pd.Series(0, index=regimes)).fillna(0)]
    ps_rop = [float(v)*100 for v in regime_compare.get("ps_avg_rop", pd.Series(0, index=regimes)).fillna(0)]
    fig5 = go.Figure()
    fig5.add_trace(go.Bar(x=regimes, y=lp_rop, name="Long Put",
        marker_color=LP_COLOR, opacity=0.9, marker_line_width=0))
    fig5.add_trace(go.Bar(x=regimes, y=ps_rop, name="Put Spread",
        marker_color=PS_COLOR, opacity=0.9, marker_line_width=0))
    fig5.add_hline(y=0, line=dict(color=FID_RULE, width=0.8))
    fig5.update_layout(**plotly_base("Return on Premium by Regime", height=320), barmode="group")
    fig5.update_yaxes(ticksuffix="%")
    fig5.update_xaxes(tickangle=-30, tickfont=dict(size=9))
    st.plotly_chart(fig5, use_container_width=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


# ── Cap Breach ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Spread Cap Breach — When the Short Strike Binds</div>',
            unsafe_allow_html=True)

ps_analysis = ps_df.copy()
ps_analysis["spot_decline_pct"] = (
    (ps_analysis["open_spot"] - ps_analysis["close_spot"]) / ps_analysis["open_spot"]
)
threshold = 1 - SHORT_STRIKE
ps_analysis["cap_hit"] = ps_analysis["spot_decline_pct"] > threshold
cap_by_regime = ps_analysis.groupby("regime")["cap_hit"].agg(["sum","count","mean"])
cap_by_regime.columns = ["cap_hits", "total_trades", "cap_hit_rate"]
cap_rates = [float(v)*100 for v in cap_by_regime["cap_hit_rate"]]
cap_regimes = cap_by_regime.index.tolist()
bar_colors = [FID_RED if r > 20 else FID_AMBER if r > 10 else FID_GREEN for r in cap_rates]

fig6 = go.Figure()
fig6.add_trace(go.Bar(
    x=cap_regimes, y=cap_rates,
    marker_color=bar_colors, opacity=0.9, marker_line_width=0,
    text=[f"{r:.1f}%" for r in cap_rates],
    textposition="outside",
    textfont=dict(size=10, color=FID_CHARCOAL),
))
fig6.update_layout(
    **plotly_base(f"Cap Breach Rate by Regime — SPY Decline > {threshold:.0%}", height=340),
    showlegend=False
)
fig6.update_yaxes(ticksuffix="%")
fig6.update_xaxes(tickangle=-30, tickfont=dict(size=9))
st.plotly_chart(fig6, use_container_width=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


# ── Trade Log ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Trade Log</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Long Put", "Put Spread"])
display_cols = ["open_date","close_date","regime","open_spot","close_spot","premium_paid","pnl","close_reason"]

with tab1:
    show = lp_df[[c for c in display_cols if c in lp_df.columns]].copy()
    show["pnl"]          = show["pnl"].map("${:,.0f}".format)
    show["premium_paid"] = show["premium_paid"].map("${:,.0f}".format)
    st.dataframe(show, use_container_width=True, height=260)

with tab2:
    show = ps_df[[c for c in display_cols if c in ps_df.columns]].copy()
    show["pnl"]          = show["pnl"].map("${:,.0f}".format)
    show["premium_paid"] = show["premium_paid"].map("${:,.0f}".format)
    st.dataframe(show, use_container_width=True, height=260)
