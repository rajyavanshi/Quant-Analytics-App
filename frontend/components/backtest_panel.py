# =====================================================
# File: frontend/components/backtest_panel.py
# Purpose: Render PnL curve, hit-rate, and summary metrics for backtests
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import numpy as np

def _ensure_df(data):
    if data is None:
        return pd.DataFrame()
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    df = pd.DataFrame(data)
    if "timestamp" in df.columns:
        try:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        except Exception:
            pass
    return df

def render_pnl_curve(df: pd.DataFrame, title="Strategy PnL Curve"):
    """
    Plot cumulative PnL (or equity curve). Expects a 'pnl' or 'equity' column in df.
    If only trade PnL rows exist, converts to cumulative series.
    """
    if df.empty:
        st.info("No backtest data available to plot PnL.")
        return

    df = df.copy()
    # detect possible columns
    if "equity" in df.columns:
        series = pd.to_numeric(df["equity"], errors="coerce")
    elif "cumulative_pnl" in df.columns:
        series = pd.to_numeric(df["cumulative_pnl"], errors="coerce")
    elif "pnl" in df.columns:
        series = pd.to_numeric(df["pnl"], errors="coerce").fillna(0).cumsum()
    else:
        st.info("No 'pnl' / 'equity' column in data. Showing first numeric column as proxy.")
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not numeric_cols:
            st.warning("No numeric columns detected for PnL.")
            return
        series = pd.to_numeric(df[numeric_cols[0]], errors="coerce").fillna(0).cumsum()

    x = df["timestamp"] if "timestamp" in df.columns else df.index

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=series, mode="lines", name="Equity / Cumulative PnL",
                             line=dict(width=2, color="#9AD0EC")))
    # draw zero line
    fig.add_hline(y=0, line_dash="dot", line_color="#666666")
    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="PnL / Equity",
        paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
        font=dict(color="#FAFAFA"),
        margin=dict(l=30, r=30, t=50, b=30),
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

def render_hit_rate_table(df: pd.DataFrame):
    """
    Expect trade-level rows with 'pnl' and 'side' columns (optional).
    Computes hit rate, avg win/loss, win:loss ratio.
    """
    if df.empty or "pnl" not in df.columns:
        st.info("No trade-level 'pnl' data available for hit-rate table.")
        return

    df = df.copy()
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0)
    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] <= 0]

    win_count = len(wins)
    loss_count = len(losses)
    total = win_count + loss_count
    hit_rate = (win_count / total) if total > 0 else None
    avg_win = wins["pnl"].mean() if not wins.empty else None
    avg_loss = losses["pnl"].mean() if not losses.empty else None
    avg_loss_abs = abs(avg_loss) if avg_loss is not None else None
    payoff = (avg_win / avg_loss_abs) if (avg_win and avg_loss_abs and avg_loss_abs != 0) else None

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades", total)
    col2.metric("Hit Rate", f"{hit_rate:.2%}" if hit_rate is not None else "N/A")
    col3.metric("Avg Win", f"{avg_win:.4f}" if avg_win is not None else "N/A")
    col4.metric("Avg Loss", f"{avg_loss:.4f}" if avg_loss is not None else "N/A")

    # show simple table of top wins and losses
    with st.expander("Top wins / losses (trade-level)"):
        wins_top = wins.sort_values("pnl", ascending=False).head(5)
        losses_top = losses.sort_values("pnl").head(5)
        st.write("Top wins")
        st.dataframe(wins_top[["timestamp", "side", "pnl"]].head(5) if not wins_top.empty else wins_top)
        st.write("Top losses")
        st.dataframe(losses_top[["timestamp", "side", "pnl"]].head(5) if not losses_top.empty else losses_top)

def render_performance_summary(df: pd.DataFrame):
    """
    High-level summary metrics: total pnl, max drawdown, annualized return (approx),
    volatility, sharpe-ish (assumes pnl series).
    """
    if df.empty:
        st.info("No backtest data to summarize.")
        return

    # try to get cumulative pnl / equity series
    if "equity" in df.columns:
        series = pd.to_numeric(df["equity"], errors="coerce").dropna()
    elif "cumulative_pnl" in df.columns:
        series = pd.to_numeric(df["cumulative_pnl"], errors="coerce").dropna()
    elif "pnl" in df.columns:
        series = pd.to_numeric(df["pnl"], errors="coerce").fillna(0).cumsum()
    else:
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not numeric_cols:
            st.info("No numeric data for performance summary.")
            return
        series = pd.to_numeric(df[numeric_cols[0]], errors="coerce").fillna(0).cumsum()

    total_pnl = series.iloc[-1] - series.iloc[0] if len(series) > 1 else series.iloc[-1]
    # max drawdown
    roll_max = series.cummax()
    drawdown = series - roll_max
    max_dd = drawdown.min()

    # approximate annualized return & vol if we have a timestamp
    days = 1
    if "timestamp" in df.columns:
        try:
            ts = pd.to_datetime(df["timestamp"].dropna())
            if len(ts) > 1:
                days = max(1, (ts.iloc[-1] - ts.iloc[0]).days)
        except Exception:
            days = 1

    annualized_return = (total_pnl / max(1, days)) * 365 if days else None
    # volatility of daily PnL approx - use differences in series
    pnl_diff = series.diff().fillna(0)
    vol = pnl_diff.std() * np.sqrt(252) if not pnl_diff.empty else None
    sharpe = (annualized_return / vol) if (vol and vol != 0) else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total PnL", f"{total_pnl:.4f}")
    c2.metric("Max Drawdown", f"{max_dd:.4f}")
    c3.metric("Annualized (approx)", f"{annualized_return:.2f}" if annualized_return is not None else "N/A")
    c4.metric("Volatility (ann.)", f"{vol:.4f}" if vol is not None else "N/A")

    if sharpe is not None:
        st.metric("Sharpe-like", f"{sharpe:.2f}")

def render_backtest_from_data(raw):
    """
    Full panel composition given raw backtest payload (list/dict/df).
    """
    df = _ensure_df(raw)
    if df.empty:
        st.info("No backtest data found.")
        return

    # show head
    st.markdown("#### Latest backtest snapshot (top rows)")
    st.dataframe(df.head(8), use_container_width=True)

    # chart + metrics
    st.markdown("---")
    render_pnl_curve(df)
    st.markdown("---")
    render_performance_summary(df)
    st.markdown("---")
    render_hit_rate_table(df)
