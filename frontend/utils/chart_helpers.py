# =====================================================
# File: frontend/utils/chart_helpers.py
# Purpose: Rolling correlation visualization with adaptive insights
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.data_processing import to_dataframe, clean_numeric


# -----------------------------------------------------
# Rolling Correlation Visualization
# -----------------------------------------------------
def plot_rolling_correlation(raw_data, window=60, symbol_x="X", symbol_y="Y"):
    """
    Compute and visualize rolling correlation between two assets.
    Includes:
      - Dynamic correlation interpretation
      - Shaded bands for correlation zones
      - Metric summaries
      - CSV export
    """
    df = to_dataframe(raw_data)
    if df.empty:
        st.warning(" No data available for rolling correlation.")
        return

    # 1️. Normalize column naming
    rename_map = {
        "price_x": "x_price", "price_y": "y_price",
        "px1": "x_price", "px2": "y_price",
        "price1": "x_price", "price2": "y_price",
        "x": "x_price", "y": "y_price",
        "symbol_x_price": "x_price", "symbol_y_price": "y_price",
    }
    df.rename(columns=rename_map, inplace=True)

    # 2️. Detect fallback price columns
    price_cols = [c for c in df.columns if "price" in c.lower() or "close" in c.lower()]
    if "x_price" not in df.columns and len(price_cols) >= 1:
        df["x_price"] = df[price_cols[0]]
    if "y_price" not in df.columns:
        if len(price_cols) >= 2:
            df["y_price"] = df[price_cols[1]]
        elif "x_price" in df.columns:
            df["y_price"] = df["x_price"]

    # 3️. Clean numeric and timestamp columns
    df = clean_numeric(df, ["x_price", "y_price"])
    if "timestamp" not in df.columns:
        df["timestamp"] = pd.RangeIndex(0, len(df))

    # 4️. Handle insufficient data
    if len(df) < window:
        st.warning(f" Only {len(df)} points available — less than rolling window = {window}. Showing static correlation.")
        corr_value = df["x_price"].corr(df["y_price"])
        st.metric("Static Correlation", f"{corr_value:.4f}" if pd.notnull(corr_value) else "N/A")
        return

    # 5️. Compute rolling correlation
    try:
        df["rolling_corr"] = df["x_price"].rolling(window=window, min_periods=1).corr(df["y_price"])
    except Exception as e:
        st.error(f"❌ Error computing rolling correlation: {e}")
        return

    # 6️. Prepare chart
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["rolling_corr"],
        mode="lines",
        name=f"Rolling Corr ({symbol_x} vs {symbol_y})",
        line=dict(color="#9AD0EC", width=2)
    ))

    # --- Add shaded zones for interpretation ---
    fig.add_hrect(y0=0.8, y1=1.0, fillcolor="#0FA3B1", opacity=0.15, line_width=0, annotation_text="High (+ve corr)", yref="y")
    fig.add_hrect(y0=-1.0, y1=-0.8, fillcolor="#E63946", opacity=0.15, line_width=0, annotation_text="High (-ve corr)", yref="y")
    fig.add_hrect(y0=-0.4, y1=0.4, fillcolor="#FFD166", opacity=0.15, line_width=0, annotation_text="Weak correlation", yref="y")

    # --- Chart styling ---
    fig.update_layout(
        title=f" Rolling Correlation — {symbol_x} vs {symbol_y} (window = {window})",
        title_x=0.5,
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#FAFAFA"),
        hovermode="x unified",
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="Timestamp", showgrid=False),
        yaxis=dict(title="Rolling Correlation", range=[-1, 1])
    )

    st.plotly_chart(fig, use_container_width=True)

    # 7️. Metrics
    latest_corr = df["rolling_corr"].iloc[-1]
    mean_corr = df["rolling_corr"].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("Latest Corr", f"{latest_corr:.4f}")
    col2.metric("Average Corr", f"{mean_corr:.4f}")
    col3.metric("Window Size", f"{window}")

    # 8️. Interpretation
    st.markdown("####  Correlation Insight")
    interpretation = ""
    if latest_corr >= 0.8:
        interpretation = f" Strong **positive** correlation — {symbol_x} and {symbol_y} move together closely."
    elif latest_corr <= -0.8:
        interpretation = f" Strong **inverse** correlation — {symbol_x} rises when {symbol_y} falls."
    elif abs(latest_corr) < 0.4:
        interpretation = " Weak correlation — potential divergence or uncorrelated movement."
    else:
        interpretation = " Moderate correlation — some co-movement, but not consistent."

    st.info(interpretation)

    st.caption("Rolling correlation helps assess co-movement strength over time — useful in pairs trading, cointegration, and portfolio diversification.")

    # 9️. Download CSV
    csv_df = df[["timestamp", "rolling_corr"]]
    st.download_button(
        " Download Rolling Corr CSV",
        data=csv_df.to_csv(index=False).encode("utf-8"),
        file_name=f"rolling_corr_{symbol_x}_{symbol_y}.csv",
        mime="text/csv",
        help="Download rolling correlation data for custom analysis."
    )
