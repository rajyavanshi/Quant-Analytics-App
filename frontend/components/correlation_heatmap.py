# =====================================================
# File: frontend/components/correlation_heatmap.py
# Purpose: Interactive correlation heatmap between symbols or price series
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# -----------------------------------------------------
# 1️⃣ — Safe Correlation Calculator
# -----------------------------------------------------
def compute_correlation_matrix(data):
    """
    Accepts:
        data: dict, list of dicts, or DataFrame
    Returns:
        Pandas correlation matrix (float values)
    """

    # Convert safely to DataFrame
    if isinstance(data, dict) and "data" in data:
        df = pd.DataFrame(data["data"])
    elif isinstance(data, (list, tuple)):
        df = pd.DataFrame(data)
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        st.warning("Unsupported data format for correlation matrix.")
        return pd.DataFrame()

    # Keep only numeric columns
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        st.warning("No numeric columns found for correlation.")
        return pd.DataFrame()

    # Compute correlation matrix (safe)
    corr_matrix = numeric_df.corr()
    return corr_matrix


# -----------------------------------------------------
# 2️⃣ — Correlation Heatmap Plotter
# -----------------------------------------------------
def plot_correlation_heatmap(data, title="Correlation Heatmap", method="pearson"):
    """
    Plots a correlation heatmap for numeric columns.
    Accepts either dict/list/df from analytics or custom data.
    """

    corr_matrix = compute_correlation_matrix(data)
    if corr_matrix.empty:
        st.info("No valid numeric data available for heatmap.")
        return

    # Recompute using selected method if specified
    if method in ["pearson", "spearman", "kendall"]:
        corr_matrix = corr_matrix.corr(method=method)

    fig = px.imshow(
        corr_matrix,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        title=title,
    )
    fig.update_layout(
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#FAFAFA"),
        margin=dict(l=40, r=40, t=60, b=40),
        title_x=0.5,
        xaxis_title=None,
        yaxis_title=None,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Inline correlation insights
    avg_corr = corr_matrix.stack().mean()
    strongest_pair = corr_matrix.unstack().sort_values(ascending=False).dropna()
    if not strongest_pair.empty:
        strongest = strongest_pair.index[0]
        st.caption(f"🔹 **Highest correlation:** {strongest[0]} ↔ {strongest[1]} = {strongest_pair.iloc[0]:.3f}")
    st.caption(f"📊 **Average correlation across all pairs:** {avg_corr:.3f}")


# -----------------------------------------------------
# 3️⃣ — Example usage (for standalone test)
# -----------------------------------------------------
if __name__ == "__main__":
    st.set_page_config(page_title="Heatmap Test", layout="wide")

    st.title("🧮 Correlation Heatmap Demo")
    st.caption("Standalone test mode — for internal debugging")

    # Create synthetic data for demonstration
    np.random.seed(42)
    df_test = pd.DataFrame({
        "BTCUSDT": np.random.randn(100).cumsum(),
        "ETHUSDT": np.random.randn(100).cumsum(),
        "BNBUSDT": np.random.randn(100).cumsum(),
        "SOLUSDT": np.random.randn(100).cumsum(),
    })

    plot_correlation_heatmap(df_test, title="Sample Symbol Correlation Heatmap")
