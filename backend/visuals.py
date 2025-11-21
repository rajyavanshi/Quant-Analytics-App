# This is just a visualization script for the alert system stage.
# It reads the generated alerts CSV and plots the z-score with trade signals.
# This  was not part of the original requirements but added for better insight.

import pandas as pd
import matplotlib.pyplot as plt

#   CSV path
file_path = r"D:\Quant Analytics App\alerts\alerts_output.csv"

# Read and preprocess
df = pd.read_csv(file_path)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.dropna(subset=['zscore'])  # remove warm-up rows

# Plot z-score line
plt.figure(figsize=(12, 6))
plt.plot(df['timestamp'], df['zscore'], label='Z-Score', linewidth=1.5)

# Highlight LONG and SHORT entries
longs = df[df['signal'] == 'LONG']
shorts = df[df['signal'] == 'SHORT']

plt.scatter(longs['timestamp'], longs['zscore'], color='green', marker='^', s=100, label='LONG Entry')
plt.scatter(shorts['timestamp'], shorts['zscore'], color='red', marker='v', s=100, label='SHORT Entry')

# Draw neutral band lines
plt.axhline(2, color='gray', linestyle='--', linewidth=1)
plt.axhline(-2, color='gray', linestyle='--', linewidth=1)

# Final formatting
plt.title("Z-Score Based Trade Signals (Stage 4: Alert System)", fontsize=14)
plt.xlabel("Timestamp")
plt.ylabel("Z-Score")
plt.legend()
plt.grid(True, linestyle='--', alpha=0.6)
plt.tight_layout()
plt.show()
