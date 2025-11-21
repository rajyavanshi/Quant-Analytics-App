# =====================================================
# File: frontend/components/settings_manager.py
# Purpose: Handle user-configurable settings for the Quant Dashboard
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
import os
import json

# -----------------------------------------------------
# Default settings (used if no session state found)
# -----------------------------------------------------
DEFAULT_SETTINGS = {
    "theme": "Dark",
    "auto_refresh": 30,
    "developer_mode": False,
    "default_data_limit": 200,
}

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "user_settings.json")


# -----------------------------------------------------
# Load settings from JSON or fallback
# -----------------------------------------------------
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            return {**DEFAULT_SETTINGS, **data}
        except Exception:
            return DEFAULT_SETTINGS.copy()
    else:
        return DEFAULT_SETTINGS.copy()


# -----------------------------------------------------
# Save settings safely
# -----------------------------------------------------
def save_settings(new_settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(new_settings, f, indent=4)


# -----------------------------------------------------
# Apply theme or runtime settings dynamically
# -----------------------------------------------------
def apply_theme(theme):
    if theme == "Light":
        st.markdown(
            """
            <style>
            body { background-color: #FFFFFF; color: #000000; }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        # already using your dark theme CSS — no runtime change needed
        pass


# -----------------------------------------------------
# Initialize and store in session
# -----------------------------------------------------
def init_settings():
    if "settings" not in st.session_state:
        st.session_state["settings"] = load_settings()
    return st.session_state["settings"]
