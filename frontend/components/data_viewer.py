# =====================================================
# File: frontend/components/data_viewer.py
# Purpose: Pretty viewer for tick / analytics / log data
# Author: Suraj Prakash (Quant Developer)
# =====================================================

import streamlit as st
import pandas as pd
from datetime import datetime

def render_json_block(data):
    st.json(data, expanded=False)

def render_dataframe_table(data, key="data_table"):
    if data is None or len(data) == 0:
        st.info("No data available.")
        return
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, key=key)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv, f"{key}_{datetime.now():%Y%m%d_%H%M}.csv", "text/csv")

def render_logs_block(lines: list):
    if not lines:
        st.info("No logs retrieved.")
        return
    st.code("\n".join(lines[-100:]), language="bash")
