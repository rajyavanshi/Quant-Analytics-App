# =====================================================
# File: frontend/components/context_blocks.py
# Purpose: Chart-level contextual commentary (Price, Spread, Corr)
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st

# -----------------------------------------------------
# Helper — styled context message renderer
# -----------------------------------------------------
def render_context_block(title: str, lines: list[str], accent: str = "#00F5D4"):
    """Reusable styled block for chart-level context."""
    html = f"""
    <div class="context-block" style="border-left: 3px solid {accent};">
        <b style="color:{accent}">{title}</b><br>
        {'<br>'.join(lines)}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# -----------------------------------------------------
# 1️⃣ Price Chart Context
# -----------------------------------------------------
def price_chart_context(symbol_x: str, symbol_y: str):
    render_context_block(
        f"📈 {symbol_x} vs {symbol_y} — Price Relationship",
        [
            "• Observe relative movement between both assets over time.",
            "• A **widening normalized gap** signals potential **divergence** (possible trade setup).",
            "• A **tight band** indicates high co-movement — stable pair relationship.",
            "• Use normalized mode (base = 100) to assess *relative strength* cleanly.",
        ],
        accent="#00F5D4"
    )


# -----------------------------------------------------
# 2️⃣ Spread + Z-score Context
# -----------------------------------------------------
def spread_chart_context():
    render_context_block(
        "🔍 Spread & Z-Score Interpretation",
        [
            "• The **spread** measures deviation between X and Y prices, adjusted by hedge ratio.",
            "• The **Z-score** standardizes this spread → how many σ away from mean.",
            "• **Z > +2 → Overbought**, potential SHORT; **Z < -2 → Oversold**, potential LONG.",
            "• Gray band between ±2σ represents neutral zone (no clear signal).",
        ],
        accent="#FFD166"
    )


# -----------------------------------------------------
# 3️⃣ Rolling Correlation Context
# -----------------------------------------------------
def corr_chart_context():
    render_context_block(
        "🔗 Rolling Correlation Context",
        [
            "• Rolling correlation shows **how tightly X and Y move together** over time.",
            "• **High (>0.8)** → strong co-movement; **Low (<0.4)** → potential decoupling.",
            "• Sudden drops in correlation often **precede spread divergence opportunities**.",
            "• Correlation is windowed — shorter windows increase responsiveness, longer = stability.",
        ],
        accent="#9AD0EC"
    )
