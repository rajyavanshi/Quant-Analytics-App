# =====================================================
# File: frontend/components/spread_chart.py
# Purpose: Interactive Spread and Z-Score Visualization (adaptive + insightful)
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.data_processing import to_dataframe, compute_spread_zscore, clean_numeric


# -----------------------------------------------------
# Safe Preprocessing
# -----------------------------------------------------
def preprocess_spread_data(raw_data, window=60):
    """
    Prepare spread + z-score data safely.
    Detects price columns dynamically and computes spread/z-score.
    """
    df = to_dataframe(raw_data)
    if df.empty:
        return pd.DataFrame()

    # 1️⃣ Rename common aliases
    rename_map = {
        "price_x": "x_price", "price_y": "y_price",
        "px1": "x_price", "px2": "y_price",
        "x": "x_price", "y": "y_price",
        "price1": "x_price", "price2": "y_price",
        "symbol_x_price": "x_price", "symbol_y_price": "y_price",
        "a_price": "x_price", "b_price": "y_price",
    }
    df.rename(columns=rename_map, inplace=True)

    # 2️⃣ Identify likely price columns
    price_cols = [c for c in df.columns if "price" in c.lower() or "close" in c.lower()]
    if "x_price" not in df.columns and len(price_cols) >= 1:
        df["x_price"] = df[price_cols[0]]
    if "y_price" not in df.columns:
        if len(price_cols) >= 2:
            df["y_price"] = df[price_cols[1]]
        elif "x_price" in df.columns:
            df["y_price"] = df["x_price"]

    # 3️⃣ Validate existence
    if "x_price" not in df.columns or "y_price" not in df.columns:
        st.warning("⚠️ Could not find valid price columns in analytics data.")
        st.dataframe(df.head(), use_container_width=True)
        return pd.DataFrame()

    # 4️⃣ Clean numeric columns
    df = clean_numeric(df, ["x_price", "y_price"])

    # 5️⃣ Add synthetic timestamp if missing
    if "timestamp" not in df.columns:
        df["timestamp"] = pd.RangeIndex(0, len(df))

    # 6️⃣ Compute spread/z-score safely
    try:
        df = compute_spread_zscore(df, "x_price", "y_price", window=window)
    except Exception as e:
        st.error(f"❌ Failed to compute spread/z-score: {e}")
        return pd.DataFrame()

    # 7️⃣ Drop invalid rows
    df = df.dropna(subset=["spread", "zscore"], how="all").reset_index(drop=True)
    return df


# -----------------------------------------------------
# Chart Renderer
# -----------------------------------------------------
def plot_spread_zscore_chart(data=None, symbol_x="X", symbol_y="Y", window=60, limit=200):
    """
    Visualizes spread and z-score for mean-reversion analytics.
    Includes:
      - Dual-axis (Spread / Z-score)
      - ±2σ threshold zones
      - Auto LONG/SHORT/NEUTRAL signal detector
      - Downloadable CSV
    """
    if data is not None:
        st.session_state["spread_raw_data"] = data
        st.session_state["spread_df_full"] = preprocess_spread_data(data, window)

    if "spread_df_full" not in st.session_state or st.session_state["spread_df_full"].empty:
        st.warning("⚠️ No valid spread data available. Please fetch analytics first.")
        return

    df_full = st.session_state["spread_df_full"]
    limit = min(int(limit), len(df_full))
    df = df_full.tail(limit).reset_index(drop=True)
    st.session_state["spread_df_plot"] = df

    # --- Plot Construction ---
    fig = go.Figure()

    # Spread (left axis)
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["spread"],
        mode="lines",
        name="Spread",
        line=dict(color="#06D6A0", width=2),
        yaxis="y1"
    ))

    # Z-score (right axis)
    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["zscore"],
        mode="lines",
        name="Z-Score",
        line=dict(color="#FFD166", width=2, dash="dot"),
        yaxis="y2"
    ))

    # ±2σ Highlight
    fig.add_hrect(y0=-2, y1=2, fillcolor="#333333", opacity=0.25, line_width=0, yref="y2")
    fig.add_hline(y=2, line_dash="dot", line_color="#FF595E", annotation_text="+2σ", yref="y2")
    fig.add_hline(y=-2, line_dash="dot", line_color="#118AB2", annotation_text="-2σ", yref="y2")

    # --- Layout ---
    layout = dict(
        title=f"📉 Spread & Z-Score — {symbol_x}/{symbol_y} (Last {limit} Records)",
        title_x=0.5,
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#FAFAFA"),
        hovermode="x unified",
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="Timestamp", showgrid=False),
        yaxis=dict(title="Spread", side="left", showgrid=False),
        yaxis2=dict(title="Z-Score", overlaying="y", side="right", showgrid=False)
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})

    # --- Summary Metrics ---
    st.markdown("#### 📊 Summary Metrics")
    spread_mean = df["spread"].mean()
    z_mean = df["zscore"].mean()
    z_latest = df["zscore"].iloc[-1]

    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Spread", f"{spread_mean:.4f}")
    c2.metric("Avg Z-Score", f"{z_mean:.3f}")
    c3.metric("Z-Score (Latest)", f"{z_latest:.3f}")

    # --- Auto Signal Detection ---
    signal = "NEUTRAL"
    color = "⚪"
    if z_latest >= 2:
        signal, color = "SHORT", "🔴"
    elif z_latest <= -2:
        signal, color = "LONG", "🟢"

    st.success(f"{color} **Current Signal:** {signal} | Z = {z_latest:.2f}")

    # --- Explanation Section ---
    st.info(
        "📈 **Interpretation:**\n\n"
        "- The **spread** represents the price difference between the two assets.\n"
        "- The **z-score** measures how far the current spread deviates from its mean.\n"
        "- Typically, |Z| > 2 suggests mean-reversion opportunities: "
        "🔴 **SHORT** if Z > +2, 🟢 **LONG** if Z < -2."
    )

    st.caption(f"Window: {window} | Records: {limit}")

    # --- CSV Download ---
    st.download_button(
        "⬇️ Download Spread-Z Data",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=f"{symbol_x}_{symbol_y}_spread_zscore.csv",
        mime="text/csv",
        help="Download current spread & z-score dataset."
    )
