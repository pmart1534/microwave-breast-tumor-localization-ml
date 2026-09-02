"""Build Fig. 3 -- per-antenna response variation.

Overlay |S11|, |S22|, |S33|, |S44| (the four antennas' reflection coefficients)
in dB from a single reference-session baseline sweep, so the reader can see
that the four hand-built antennas have visibly different signal responses --
motivating the antenna-swap experiment.

Data: mean of the 16 baseline_T*.csv sweeps from a single Aug18 same-day
reference session (Session0101_20260818_1143), which is one of the three
'reference (no drift)' sessions.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

SESS = Path(r"C:\Users\peter\Desktop\EM Imaging\BreastPhantom\HunterVNA\DataMeasurements\Sam Antennas\MediumAntenna\Separated\Aug18\A3_SamMed_MetalTumor_Session0101_20260818_1143")
OUT  = Path(r"C:\Users\peter\Desktop\EM Imaging\Research Paper\Major Revision Round 1\Images\Fig3_antenna_response_variation.png")

# ------------------------------------------------------------------
# Load the 16 baseline sweeps and average them
baseline_files = sorted(SESS.glob("baseline_T*.csv"))
print(f"found {len(baseline_files)} baseline files")
if not baseline_files:
    raise SystemExit("no baseline files found; adjust the path")

# Read one to get the column layout
df0 = pd.read_csv(baseline_files[0])
print("columns:", list(df0.columns)[:10], "...", len(df0.columns), "total")
freqs = df0["Frequency"].values.astype(float)
n_freq = len(freqs)
print(f"freq points: {n_freq}, range {freqs[0]/1e9:.3f}-{freqs[-1]/1e9:.3f} GHz")

# Collect S11, S22, S33, S44 magnitudes across the 16 baseline files
# Columns are named: S1-1, P1-1, S2-1, P2-1, ..., meaning S[from]-[to] as
# magnitude and P[from]-[to] as phase in degrees.  So Sii magnitudes are
# columns "S1-1", "S2-2", "S3-3", "S4-4".
mag_cols = [f"S{i}-{i}" for i in range(1, 5)]
mags = np.zeros((len(baseline_files), 4, n_freq))
for k, f in enumerate(baseline_files):
    df = pd.read_csv(f)
    for j, col in enumerate(mag_cols):
        mags[k, j, :] = df[col].values.astype(float)
# Convert to dB and average across the 16 baseline sweeps
mags_db = 20 * np.log10(np.clip(mags, 1e-6, None))
mag_mean_db = mags_db.mean(axis=0)   # (4, n_freq)

# L2 pairwise distance between the four antennas' |Sii| curves in dB
pairs = []
for i in range(4):
    for j in range(i + 1, 4):
        d = np.sqrt(np.mean((mag_mean_db[i] - mag_mean_db[j]) ** 2))
        pairs.append(((i + 1, j + 1), d))
        print(f"|S{i+1}{i+1}| vs |S{j+1}{j+1}|: RMS dB distance = {d:.2f}")
mean_L2 = np.mean([d for _, d in pairs])
print(f"mean pairwise RMS distance = {mean_L2:.2f} dB")

# Plot -- Wong / Okabe-Ito colorblind-safe palette, solid lines, distinct markers
COLORS  = ["#0072B2", "#E69F00", "#009E73", "#CC79A7"]  # blue, orange, green, pink
MARKERS = ["o",       "s",       "^",        "D"]        # circle, square, triangle, diamond

fig, ax = plt.subplots(figsize=(7.4, 4.2), dpi=180)
freqs_ghz = freqs / 1e9
# Space markers along each curve so they don't clutter
n_markers = 24
marker_idx = np.linspace(0, n_freq - 1, n_markers).astype(int)
for i in range(4):
    ax.plot(freqs_ghz, mag_mean_db[i],
            color=COLORS[i], linestyle="-", linewidth=1.8,
            marker=MARKERS[i], markersize=6,
            markevery=list(marker_idx), markerfacecolor=COLORS[i],
            markeredgecolor="black", markeredgewidth=0.6,
            label=f"|S{i+1}{i+1}|  (antenna {i+1})")

ax.set_xlabel("Frequency (GHz)", fontsize=11)
ax.set_ylabel("Reflection coefficient magnitude (dB)", fontsize=11)
ax.set_xlim(0, 8)
# no plot title -- IEEE JERM style puts it in the figure caption
ax.grid(True, linestyle=":", alpha=0.5)
ax.legend(loc="lower right", frameon=False, fontsize=9)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(OUT, facecolor="white")
plt.close(fig)
print(f"wrote {OUT}")
