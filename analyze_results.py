"""
analyze_results.py

Loads results.csv and produces a multi-panel visualization to help
an engineer decide where the optimal operating point is and where
to look next.

Panels:
  1. SNR heatmap  — eq_gain vs tx_level (best pre_emphasis per cell)
  2. SNR vs tx_level — line per eq_gain value (best pre_emphasis per combo)
  3. SNR vs pre_emphasis — for top-3 tx/eq combos
  4. Correlation matrix — SNR, eye_height_mv, eye_width_ps, log10(BER)
  5. BER vs SNR scatter with passing/failing coloring
  6. Phase comparison — box plot of SNR for Phase 1 vs Phase 2

Usage:
    python analyze_results.py              # saves results_analysis.png
    python analyze_results.py --show       # also opens interactive window
"""

import sys
import math
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

RESULTS_FILE = "results.csv"
OUTPUT_FILE  = "results_analysis.png"


# ---------------------------------------------------------------------------
# Load & clean
# ---------------------------------------------------------------------------
df = pd.read_csv(RESULTS_FILE)

# Keep only rows with valid measurements
df_pass = df[df["status"].isin(["PASS", "OUT_OF_RANGE"])].copy()
df_pass["snr_db"]        = pd.to_numeric(df_pass["snr_db"],        errors="coerce")
df_pass["eye_height_mv"] = pd.to_numeric(df_pass["eye_height_mv"], errors="coerce")
df_pass["eye_width_ps"]  = pd.to_numeric(df_pass["eye_width_ps"],  errors="coerce")
df_pass["ber"]           = pd.to_numeric(df_pass["ber"],           errors="coerce")
df_pass["log_ber"]       = np.log10(df_pass["ber"].clip(lower=1e-15))
df_pass = df_pass.dropna(subset=["snr_db"])

if df_pass.empty:
    print("No passing measurements found in results.csv — check your data.")
    sys.exit(1)

best_row = df_pass.loc[df_pass["snr_db"].idxmax()]
print(f"Best operating point:")
print(f"  tx_level={int(best_row['tx_level'])}, eq_gain={int(best_row['eq_gain'])}, "
      f"pre_emphasis={int(best_row['pre_emphasis'])}")
print(f"  SNR={best_row['snr_db']:.2f} dB  |  "
      f"eye_h={best_row['eye_height_mv']:.1f} mV  |  "
      f"eye_w={best_row['eye_width_ps']:.1f} ps  |  "
      f"BER={best_row['ber']:.2e}")


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
fig = plt.figure(figsize=(16, 14))
fig.suptitle("ODVT Device Characterisation — Parameter Sweep Analysis",
             fontsize=14, fontweight="bold", y=0.98)

gs = fig.add_gridspec(3, 3, hspace=0.45, wspace=0.38)
ax1 = fig.add_subplot(gs[0, 0:2])   # SNR heatmap (wide)
ax2 = fig.add_subplot(gs[0, 2])     # SNR vs pre_emphasis
ax3 = fig.add_subplot(gs[1, 0])     # SNR vs tx_level
ax4 = fig.add_subplot(gs[1, 1])     # SNR vs eq_gain
ax5 = fig.add_subplot(gs[1, 2])     # BER vs SNR scatter
ax6 = fig.add_subplot(gs[2, 0:2])   # Correlation heatmap (wide)
ax7 = fig.add_subplot(gs[2, 2])     # Phase comparison


# --- 1. SNR Heatmap: eq_gain vs tx_level (max SNR across pre_emphasis) ------
pivot = (df_pass.groupby(["tx_level", "eq_gain"])["snr_db"]
                .max().reset_index()
                .pivot(index="eq_gain", columns="tx_level", values="snr_db"))

im = ax1.imshow(pivot.values, aspect="auto", cmap="gray",
                origin="lower",
                extent=[pivot.columns.min()-5, pivot.columns.max()+5,
                        pivot.index.min()-0.5, pivot.index.max()+0.5])
ax1.set_xlabel("tx_level")
ax1.set_ylabel("eq_gain")
ax1.set_title("Peak SNR (dB) Heatmap\n(best pre_emphasis per cell)", fontsize=10)
cbar = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
cbar.set_label("SNR (dB)", fontsize=8)

# Mark best cell
best_tx  = int(best_row["tx_level"])
best_eq  = int(best_row["eq_gain"])
ax1.plot(best_tx, best_eq, marker="*", markersize=14, color="black",
         label=f"Best: tx={best_tx}, eq={best_eq}")
ax1.legend(fontsize=8, loc="upper left")

# Add cell value labels
for tx_idx, tx_val in enumerate(pivot.columns):
    for eq_idx, eq_val in enumerate(pivot.index):
        val = pivot.loc[eq_val, tx_val]
        if not math.isnan(val):
            ax1.text(tx_val, eq_val, f"{val:.0f}",
                     ha="center", va="center", fontsize=6,
                     color="white" if val < pivot.values[~np.isnan(pivot.values)].mean() else "black")


# --- 2. SNR vs pre_emphasis for top combos ---------------------------------
top_combos = (df_pass.groupby(["tx_level","eq_gain"])["snr_db"]
                     .max().nlargest(4).index.tolist())
for tx_val, eq_val in top_combos:
    sub = df_pass[(df_pass["tx_level"]==tx_val) & (df_pass["eq_gain"]==eq_val)]
    sub = sub.sort_values("pre_emphasis")
    ax2.plot(sub["pre_emphasis"], sub["snr_db"],
             marker="o", markersize=5,
             label=f"tx={tx_val} eq={eq_val}")

ax2.set_xlabel("pre_emphasis")
ax2.set_ylabel("SNR (dB)")
ax2.set_title("SNR vs pre_emphasis\n(top tx/eq combos)", fontsize=10)
ax2.legend(fontsize=7)
ax2.grid(True, linestyle="--", alpha=0.4)


# --- 3. SNR vs tx_level by eq_gain -----------------------------------------
for eq_val in sorted(df_pass["eq_gain"].unique()):
    sub = (df_pass[df_pass["eq_gain"]==eq_val]
           .groupby("tx_level")["snr_db"].max().reset_index()
           .sort_values("tx_level"))
    ax3.plot(sub["tx_level"], sub["snr_db"],
             marker=".", label=f"eq={eq_val}")

ax3.axhline(8.0, color="black", linestyle="--", linewidth=1, label="8 dB threshold")
ax3.set_xlabel("tx_level")
ax3.set_ylabel("SNR (dB)")
ax3.set_title("SNR vs tx_level\n(by eq_gain, best pre_emphasis)", fontsize=10)
ax3.legend(fontsize=7, ncol=2)
ax3.grid(True, linestyle="--", alpha=0.4)


# --- 4. SNR vs eq_gain by tx_level -----------------------------------------
for tx_val in sorted(df_pass["tx_level"].unique()):
    sub = (df_pass[df_pass["tx_level"]==tx_val]
           .groupby("eq_gain")["snr_db"].max().reset_index()
           .sort_values("eq_gain"))
    ax4.plot(sub["eq_gain"], sub["snr_db"],
             marker=".", label=f"tx={tx_val}")

ax4.axhline(8.0, color="black", linestyle="--", linewidth=1)
ax4.set_xlabel("eq_gain")
ax4.set_ylabel("SNR (dB)")
ax4.set_title("SNR vs eq_gain\n(by tx_level, best pre_emphasis)", fontsize=10)
ax4.legend(fontsize=6, ncol=2)
ax4.grid(True, linestyle="--", alpha=0.4)


# --- 5. BER vs SNR scatter --------------------------------------------------
colors = df_pass["status"].map({"PASS": "black", "OUT_OF_RANGE": "gray"})
ax5.scatter(df_pass["snr_db"], df_pass["log_ber"],
            c=colors, s=18, alpha=0.6, edgecolors="none")
ax5.set_xlabel("SNR (dB)")
ax5.set_ylabel("log₁₀(BER)")
ax5.set_title("BER vs SNR\n(● PASS  ● OUT_OF_RANGE)", fontsize=10)
ax5.grid(True, linestyle="--", alpha=0.4)

from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0],[0], marker='o', color='w', markerfacecolor='black', markersize=7, label='PASS'),
    Line2D([0],[0], marker='o', color='w', markerfacecolor='gray',  markersize=7, label='OUT_OF_RANGE'),
]
ax5.legend(handles=legend_elements, fontsize=8)


# --- 6. Correlation matrix --------------------------------------------------
corr_cols = ["snr_db", "eye_height_mv", "eye_width_ps", "log_ber"]
corr_labels = ["SNR (dB)", "Eye Height\n(mV)", "Eye Width\n(ps)", "log₁₀(BER)"]
corr_df = df_pass[corr_cols].dropna()
corr = corr_df.corr()

im2 = ax6.imshow(corr.values, cmap="gray", vmin=-1, vmax=1, aspect="auto")
ax6.set_xticks(range(len(corr_cols)))
ax6.set_yticks(range(len(corr_cols)))
ax6.set_xticklabels(corr_labels, fontsize=8)
ax6.set_yticklabels(corr_labels, fontsize=8)
ax6.set_title("Metric Correlation Matrix", fontsize=10)
fig.colorbar(im2, ax=ax6, fraction=0.046, pad=0.04)

for i in range(len(corr_cols)):
    for j in range(len(corr_cols)):
        val = corr.values[i, j]
        ax6.text(j, i, f"{val:.2f}", ha="center", va="center",
                 fontsize=9, color="white" if abs(val) > 0.5 else "black")


# --- 7. Phase 1 vs Phase 2 SNR box plot ------------------------------------
phase_data = []
phase_labels = []
for ph in sorted(df_pass["phase"].dropna().unique()):
    vals = df_pass[df_pass["phase"]==ph]["snr_db"].dropna().values
    if len(vals) > 0:
        phase_data.append(vals)
        phase_labels.append(f"Phase {int(ph)}")

if len(phase_data) >= 2:
    bp = ax7.boxplot(phase_data, labels=phase_labels, patch_artist=True,
                     medianprops=dict(color="black", linewidth=2))
    for patch in bp["boxes"]:
        patch.set_facecolor("lightgray")
    ax7.axhline(8.0, color="black", linestyle="--", linewidth=1, label="8 dB threshold")
    ax7.set_ylabel("SNR (dB)")
    ax7.set_title("Phase 1 vs Phase 2\nSNR Distribution", fontsize=10)
    ax7.legend(fontsize=8)
    ax7.grid(True, axis="y", linestyle="--", alpha=0.4)
else:
    ax7.text(0.5, 0.5, "Phase comparison\nnot available\n(single-phase data)",
             ha="center", va="center", transform=ax7.transAxes)
    ax7.axis("off")


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches="tight",
            facecolor="white", edgecolor="none")
print(f"\nPlot saved to {OUTPUT_FILE}")

if "--show" in sys.argv:
    matplotlib.use("TkAgg")
    plt.show()
