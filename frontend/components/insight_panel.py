# =====================================================
# File: frontend/components/insight_panel.py
# Purpose: Generate dynamic quant commentary from analytics metrics
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st

# -----------------------------------------------------
# Auto Insights Generator
# -----------------------------------------------------
def render_auto_insights(zscore=None, corr=None, adf_p=None, hedge_ratio=None, pair="N/A"):
    """
    Generate context-aware quantitative commentary from analytics metrics.
    Produces an interpretable narrative summary for the user.
    """
    insights = []

    # 1️⃣ Z-Score Interpretation
    if zscore is not None:
        if zscore > 2:
            insights.append("🔴 **Overbought spread** detected — potential SHORT entry signal.")
        elif zscore < -2:
            insights.append("🟢 **Oversold spread** detected — potential LONG entry signal.")
        else:
            insights.append("⚪ Spread within neutral zone (|Z| < 2) — no strong reversion trigger yet.")

    # 2️⃣ ADF Stationarity Check
    if adf_p is not None:
        if adf_p < 0.05:
            insights.append("✅ Series appears **stationary** (ADF p < 0.05) — supports mean-reversion validity.")
        else:
            insights.append("⚠️ Series may be **non-stationary** — statistical arbitrage signals may not hold.")

    # 3️⃣ Correlation Analysis
    if corr is not None:
        if corr > 0.8:
            insights.append("🔗 Strong **positive correlation** (> 0.8) — pair moves closely together.")
        elif corr < -0.5:
            insights.append("⚔️ Strong **inverse correlation** (< -0.5) — assets move in opposite directions.")
        elif corr < 0.4:
            insights.append("🟡 Weak correlation (< 0.4) — potential pair decoupling observed.")
        else:
            insights.append("⚪ Moderate correlation — co-movement with some divergence.")

    # 4️⃣ Hedge Ratio Note
    if hedge_ratio is not None:
        insights.append(f"⚖️ Current hedge ratio ≈ **{hedge_ratio:.3f}** — maintain this weight for neutrality.")

    # 5️⃣ Combined Market Narrative
    summary = []
    if zscore is not None and adf_p is not None:
        if abs(zscore) > 2 and adf_p < 0.05:
            direction = "LONG" if zscore < 0 else "SHORT"
            summary.append(
                f"🚀 **Quant Summary:** {pair} exhibits a strong {direction} mean-reversion setup — "
                f"Z = {zscore:.2f}, ADF p = {adf_p:.3f}, Corr = {corr:.2f if corr else 'N/A'}."
            )
        elif abs(zscore) < 1 and corr and corr > 0.7:
            summary.append(
                f"🔁 **Neutral Regime:** Spread stabilized around mean (Z ≈ {zscore:.2f}). "
                "No immediate arbitrage edge."
            )

    # 6️⃣ Render Block
    st.markdown("### 💬 Auto-Generated Quant Insights")

    html = "<div class='context-block'>" + "<br>".join(insights)
    if summary:
        html += "<hr style='opacity:0.2;'>" + "<b>" + "<br>".join(summary) + "</b>"
    html += "</div>"

    st.markdown(html, unsafe_allow_html=True)
