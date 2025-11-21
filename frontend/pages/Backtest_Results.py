# =====================================================
# File: frontend/pages/5 _Backtest_Results.py
# Purpose: Display backtest metrics, PnL curve, and trades summary
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from components.api_client import get_backtest_results

st.title(" Backtest Performance Results")

# Fetch Data
res = get_backtest_results()
if not res or res.get("status") != "success":
    st.error(" Failed to load backtest results. Please run your backtest engine first.")
    st.stop()

data = res.get("data", [])
metrics = res.get("metrics", {})

if len(data) == 0:
    st.warning("No backtest records available.")
    st.stop()

df = pd.DataFrame(data)

# ---- Metrics Summary ----
st.subheader(" Summary Metrics")
cols = st.columns(3)
cols[0].metric("Total PnL ($)", f"{metrics.get('total_pnl', 0):,.2f}")
cols[1].metric("Sharpe Ratio", f"{metrics.get('sharpe', 0):.2f}")
cols[2].metric("Win Rate", f"{metrics.get('win_rate', 0)*100:.1f}%")
cols = st.columns(3)
cols[0].metric("Max Drawdown ($)", f"{metrics.get('max_drawdown', 0):,.2f}")
cols[1].metric("Number of Trades", metrics.get("n_trades", 0))
cols[2].metric("Avg Trade PnL ($)", f"{metrics.get('avg_trade_pnl', 0):.2f}")

# ---- Plot PnL ----
st.subheader(" Cumulative PnL Curve")
fig = px.line(df, x="timestamp", y="cum_pnl", title="Cumulative PnL Over Time")
st.plotly_chart(fig, use_container_width=True)

# ---- Trades Detail ----
st.subheader(" Trades (Last 100 rows)")
st.dataframe(df.tail(100))
