# =====================================================
# File: frontend/pages/4_Settings.py
# Purpose: User configuration and preferences panel
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
from components.settings_manager import init_settings, save_settings, apply_theme

st.set_page_config(page_title=" Settings", layout="wide")

# Load / Initialize settings
settings = init_settings()

st.title(" Application Settings & Preferences")
st.caption("Customize your Quant Analytics Dashboard experience.")
st.markdown("---")

# -----------------------------------------------------
# Section 1 — Theme
# -----------------------------------------------------
st.subheader(" Theme & UI Preferences")

col1, col2 = st.columns([1, 2])
with col1:
    theme_choice = st.radio("Select Theme", ["Dark", "Light"], index=0 if settings["theme"] == "Dark" else 1)
with col2:
    if st.button("Apply Theme", use_container_width=True):
        settings["theme"] = theme_choice
        apply_theme(theme_choice)
        save_settings(settings)
        st.success(f"Theme switched to {theme_choice} mode.")

st.markdown("---")

# -----------------------------------------------------
# Section 2 — Auto Refresh & Data Settings
# -----------------------------------------------------
st.subheader(" Data Refresh & Fetch Configuration")

settings["auto_refresh"] = st.slider("Default Auto-Refresh Interval (seconds)", 10, 120, settings["auto_refresh"], step=5)
settings["default_data_limit"] = st.number_input("Default Data Fetch Limit", min_value=50, max_value=5000, value=settings["default_data_limit"], step=50)

st.markdown("---")

# -----------------------------------------------------
# Section 3 — Developer Mode
# -----------------------------------------------------
st.subheader(" Developer Mode")

settings["developer_mode"] = st.checkbox("Enable Developer Mode (show debug panels)", value=settings["developer_mode"])
if settings["developer_mode"]:
    st.info("Developer mode enabled — debug info and raw JSON responses will be visible.")

st.markdown("---")

# -----------------------------------------------------
# Section 4 — Save / Reset
# -----------------------------------------------------
colA, colB = st.columns([1, 1])
with colA:
    if st.button(" Save Settings", use_container_width=True):
        save_settings(settings)
        st.success("Settings saved successfully.")
with colB:
    if st.button(" Reset to Default", use_container_width=True):
        from components.settings_manager import DEFAULT_SETTINGS
        save_settings(DEFAULT_SETTINGS.copy())
        st.session_state["settings"] = DEFAULT_SETTINGS.copy()
        st.success("Settings reset to default. Please reload the app.")
