# =====================================================
# File: frontend/components/price_chart.py
# Purpose: Interactive price-time chart with dual axis, normalization & user clarity
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.data_processing import to_dataframe, clean_numeric


# -----------------------------------------------------
# Helper Functions
# -----------------------------------------------------
def first_valid(series):
    """Return the first valid non-null numeric value."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    return s.iloc[0] if len(s) > 0 else None


def normalize(series):
    """Normalize a price series safely to base = 100."""
    base = first_valid(series)
    if base in (None, 0):
        return pd.Series([None] * len(series))
    return (series / base) * 100


# -----------------------------------------------------
# Preprocessing (Adaptive)
# -----------------------------------------------------
def preprocess_data(raw_data):
    """Convert API response into a clean DataFrame ready for price plotting."""
    df = to_dataframe(raw_data)
    if df.empty:
        return pd.DataFrame()

    # Step 1: Rename common price keys
    rename_map = {
        "price_x": "x_price", "price_y": "y_price",
        "px1": "x_price", "px2": "y_price",
        "x": "x_price", "y": "y_price",
        "price1": "x_price", "price2": "y_price",
        "symbol_x_price": "x_price", "symbol_y_price": "y_price",
        "a_price": "x_price", "b_price": "y_price",
        "priceA": "x_price", "priceB": "y_price"
    }
    df.rename(columns=rename_map, inplace=True)

    # Step 2: Detect likely price columns
    price_cols = [c for c in df.columns if "price" in c.lower() or "close" in c.lower()]
    if "x_price" not in df.columns and len(price_cols) >= 1:
        df["x_price"] = df[price_cols[0]]
    if "y_price" not in df.columns:
        if len(price_cols) >= 2:
            df["y_price"] = df[price_cols[1]]
        elif "x_price" in df.columns:
            df["y_price"] = df["x_price"]  # fallback

    if "x_price" not in df.columns or "y_price" not in df.columns:
        st.warning("⚠️ Could not identify 'x_price' and 'y_price' columns.")
        st.dataframe(df.head(), use_container_width=True)
        return pd.DataFrame()

    # Step 3: Clean numeric columns and timestamp
    df = clean_numeric(df, ["x_price", "y_price"])
    if "timestamp" not in df.columns:
        df["timestamp"] = pd.RangeIndex(0, len(df))

    df = df.dropna(subset=["x_price", "y_price"], how="all").reset_index(drop=True)
    return df


# -----------------------------------------------------
# Main Plot Function
# -----------------------------------------------------
def plot_price_chart(data=None, symbol_x="X", symbol_y="Y", limit=200):
    """
    Displays interactive Plotly chart comparing two assets.
    Includes normalization, dual-axis logic, and CSV export.
    """
    # Store / load data in session
    if data is not None:
        st.session_state["raw_data"] = data
        st.session_state["df_full"] = preprocess_data(data)

    if "df_full" not in st.session_state or st.session_state["df_full"].empty:
        st.warning("⚠️ No valid data available. Please fetch analytics first.")
        return

    df_full = st.session_state["df_full"]
    limit = int(limit)
    limit = min(limit, len(df_full))
    df = df_full.tail(limit).reset_index(drop=True)
    st.session_state["df_plot"] = df

    # --- Mode selector ---
    st.markdown("#### 🎚️ Price View Mode")
    mode = st.radio(
        "",
        ["Raw Prices", "Normalized (Base = 100)"],
        horizontal=True,
        key="price_view_mode",
    )

    # --- Data prep ---
    df_plot = df.copy()
    if mode == "Normalized (Base = 100)":
        x_plot = normalize(df_plot["x_price"])
        y_plot = normalize(df_plot["y_price"])
        if x_plot.isnull().all() or y_plot.isnull().all():
            st.error("⚠️ Normalization failed — displaying raw prices instead.")
            x_plot, y_plot, dual_axis, ytitle = df_plot["x_price"], df_plot["y_price"], True, "Price"
        else:
            dual_axis, ytitle = False, "Normalized (Base = 100)"
    else:
        x_plot, y_plot, dual_axis, ytitle = df_plot["x_price"], df_plot["y_price"], True, "Price"

    # --- Plotly chart ---
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_plot["timestamp"],
        y=x_plot,
        mode="lines",
        name=f"{symbol_x}",
        line=dict(width=2, color="#00F5D4"),
        yaxis="y1"
    ))
    fig.add_trace(go.Scatter(
        x=df_plot["timestamp"],
        y=y_plot,
        mode="lines",
        name=f"{symbol_y}",
        line=dict(width=2, color="#FFD166"),
        yaxis="y2" if dual_axis else "y1"
    ))

    layout = dict(
        title=f"📈 {symbol_x} vs {symbol_y} — {mode} (Last {limit} Records)",
        title_x=0.5,
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#FAFAFA"),
        hovermode="x unified",
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="Timestamp", showgrid=False),
        yaxis=dict(title=ytitle if not dual_axis else f"{symbol_x} Price", side="left", showgrid=False)
    )
    if dual_axis:
        layout["yaxis2"] = dict(title=f"{symbol_y} Price", overlaying="y", side="right", showgrid=False)

    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})

    # --- Download CSV ---
    csv_data = df_plot.assign(x_plot=x_plot, y_plot=y_plot)
    st.download_button(
        "⬇️ Download Chart Data",
        data=csv_data.to_csv(index=False).encode("utf-8"),
        file_name=f"{symbol_x}_{symbol_y}_price_chart.csv",
        mime="text/csv",
        help="Download the currently displayed price data."
    )

    # --- Explanation block ---
    st.info(
        f"📊 **Interpretation:** This chart visualizes the time-series relationship between "
        f"**{symbol_x}** and **{symbol_y}**. "
        f"When normalized, both series start at 100, allowing easy comparison of relative movement "
        f"and co-integration strength over time."
    )

    st.caption(f"Showing last {limit} records | Mode: {mode}")
