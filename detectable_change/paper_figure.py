"""
paper_figure.py
===============
Renders the final detectable-change figure used in the J-ERM paper (Fig. 4):
a 3-row x 2-column grid showing, for each phantom configuration (Empty A2,
A2+F4, A2+F5) and each S-parameter (|S11|, |S12|):

  - Dot color  = detectable change Z(p) in dB (warmer = bigger physical change).
  - Dot size   = within-session CNN per-position accuracy (bigger = more accurate).
  - Black bars = antenna positions.
  - Solid ellipse + dashed polygon = adipose bowl and glandular insert outlines.

Inputs (must already exist before running this script):
  results/detectable_diff_A2_Empty.npz   produced by detectable_difference.py
  results/detectable_diff_A2_F4.npz
  results/detectable_diff_A2_F5.npz
  accuracy_data/per_position_accuracy_A2_Empty.csv  produced by parse_accuracy_txt.py
  accuracy_data/per_position_accuracy_A2_F4.csv
  accuracy_data/per_position_accuracy_A2_F5.csv
  position_adjustments.json                       hand-set tumor position overrides
                                                  (produced by calibration/adjust_positions.py)

Output: figures/paper_figure.png
"""
from __future__ import annotations
import os, csv, re, json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import Rectangle, Polygon, Ellipse

HERE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(HERE, "results")
ACC_DIR = os.path.join(HERE, "accuracy_data")
OUT_DIR = os.path.join(HERE, "figures")
os.makedirs(OUT_DIR, exist_ok=True)

SETUPS = [
    ("A2_Empty", "Empty A2", "empty"),
    ("A2_F4",    "A2 + F4", "F4"),
    ("A2_F5",    "A2 + F5", "F5"),
]
SPARAMS = ("S11", "S12")
LIMS = {"S11": (-90, -25), "S12": (-90, -25)}
CMAP = "jet"

# ------------------------------------------------------------------------------
# Phantom outline constants (traced from calibrated photos; see calibration/).
# ------------------------------------------------------------------------------
BOWL_ELLIPSE_CENTER = (2.949, 3.030)
BOWL_ELLIPSE_RX     = 2.419
BOWL_ELLIPSE_RY     = 2.576

F4_OUTLINE = [
    (2.42, 3.04), (2.35, 2.89), (2.30, 2.71), (2.33, 2.54),
    (2.34, 2.35), (2.39, 2.13), (2.44, 1.86), (2.60, 1.67),
    (2.84, 1.64), (3.08, 1.71), (3.29, 1.87), (3.42, 2.24),
    (3.50, 2.40), (3.58, 2.47), (3.67, 2.51), (3.76, 2.57),
    (3.86, 2.63), (3.97, 2.69), (4.08, 2.78), (4.18, 2.90),
    (4.30, 3.04), (4.46, 3.22), (4.49, 3.42), (4.48, 3.64),
    (4.42, 3.86), (4.33, 4.07), (4.20, 4.29), (3.95, 4.32),
    (3.68, 4.24), (3.48, 4.21), (3.29, 4.14), (3.13, 4.05),
    (2.99, 3.97), (2.86, 3.89), (2.75, 3.79), (2.67, 3.66),
    (2.60, 3.54), (2.57, 3.41), (2.50, 3.29), (2.46, 3.17),
]
F5_OUTLINE = [
    (1.44, 3.38), (1.47, 3.12), (1.55, 2.88), (1.70, 2.67),
    (1.86, 2.49), (1.94, 2.23), (2.04, 1.94), (2.27, 1.77),
    (2.53, 1.67), (2.78, 1.48), (3.08, 1.35), (3.39, 1.46),
    (3.65, 1.63), (3.90, 1.78), (4.12, 1.95), (4.26, 2.21),
    (4.35, 2.46), (4.40, 2.71), (4.44, 2.94), (4.51, 3.15),
    (4.56, 3.38), (4.53, 3.61), (4.51, 3.84), (4.50, 4.10),
    (4.52, 4.42), (4.29, 4.59), (3.99, 4.62), (3.76, 4.70),
    (3.56, 4.85), (3.35, 5.05), (3.08, 5.23), (2.80, 5.18),
    (2.58, 4.93), (2.36, 4.79), (2.16, 4.65), (1.97, 4.49),
    (1.74, 4.35), (1.59, 4.14), (1.51, 3.89), (1.44, 3.64),
]

# ------------------------------------------------------------------------------
# Data loaders
# ------------------------------------------------------------------------------
def load_setup(name):
    """Read detectable_diff_<name>.npz; return per-S-parameter labels, X, Y, Z."""
    npz_path = os.path.join(RES_DIR, f"detectable_diff_{name}.npz")
    npz = np.load(npz_path, allow_pickle=True)
    out = {}
    for s in SPARAMS:
        rows = npz[f"rows_{s}"].tolist()
        out[s] = {
            "labels": [r[0] for r in rows],
            "X": np.array([r[1] for r in rows], dtype=float),
            "Y": np.array([r[2] for r in rows], dtype=float),
            "Z": np.array([r[3] for r in rows], dtype=float),
        }
    return out

def load_accuracy(name):
    """Read per_position_accuracy_<name>.csv -> {position_label: accuracy}."""
    csv_path = os.path.join(ACC_DIR, f"per_position_accuracy_{name}.csv")
    if not os.path.exists(csv_path):
        print(f"[!] missing {csv_path}; positions for {name} will be skipped")
        return {}
    out = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            v = row.get("accuracy", "").strip()
            if not v:
                continue
            try:
                out[row["label"]] = float(v)
            except ValueError:
                pass
    return out

# Sub-position to corner-direction mapping for shrinking dots toward cell center.
SIGN = {1: (-1, -1), 2: (+1, -1), 3: (+1, +1), 4: (-1, +1)}
HALF_CELL = 0.375
SHRINK_TO_CENTER = 0.20

def shrink_positions(labels, X, Y, shrink=SHRINK_TO_CENTER):
    """Pull each dot from its physical corner toward the cell center by
    `shrink` (0 = corners untouched; 1 = collapse to center) so that
    overlapping corners stay visually distinguishable."""
    nX, nY = np.array(X, dtype=float).copy(), np.array(Y, dtype=float).copy()
    for i, L in enumerate(labels):
        m = re.match(r"R(\d+)C(\d+)P(\d+)", str(L))
        if not m:
            continue
        sub = int(m.group(3))
        sx, sy = SIGN.get(sub, (0, 0))
        cx = X[i] - sx * HALF_CELL
        cy = Y[i] - sy * HALF_CELL
        nX[i] = X[i] + shrink * (cx - X[i])
        nY[i] = Y[i] + shrink * (cy - Y[i])
    return nX, nY

# ------------------------------------------------------------------------------
# Decorators (antennas + phantom outline)
# ------------------------------------------------------------------------------
def draw_antennas(ax, xlim, ylim_inv, pad):
    xL, xR = xlim[0] + pad, xlim[1] - pad
    yC = (ylim_inv[0] + ylim_inv[1]) / 2.0
    for xface, sign in [(xL, -1), (xR, +1)]:
        x0 = xface + sign * 0.08
        x1 = xface + sign * 0.45
        ax.add_patch(Rectangle((min(x0, x1), yC - 0.55),
                               abs(x1 - x0), 1.1,
                               facecolor="black", edgecolor="black"))

def draw_phantom_outline(ax, kind, color="0.25", lw=1.1):
    """Overlay the adipose bowl ellipse and, for F4/F5, the glandular insert
    outline as a dashed polygon."""
    bowl = Ellipse(BOWL_ELLIPSE_CENTER,
                   2 * BOWL_ELLIPSE_RX, 2 * BOWL_ELLIPSE_RY,
                   fill=False, edgecolor=color, linewidth=lw, linestyle="-")
    ax.add_patch(bowl)
    pts = None
    if kind == "F4":
        pts = F4_OUTLINE
    elif kind == "F5":
        pts = F5_OUTLINE
    if pts is not None:
        poly = Polygon(pts, closed=True, fill=False,
                       edgecolor=color, linewidth=lw, linestyle=(0, (4, 2)))
        ax.add_patch(poly)

# ------------------------------------------------------------------------------
# Main figure
# ------------------------------------------------------------------------------
def main():
    DATA = {name: load_setup(name) for name, _, _ in SETUPS}
    ACC  = {name: load_accuracy(name) for name, _, _ in SETUPS}

    # Optional tumor-position overrides from calibration/adjust_positions.py.
    adj_path = os.path.join(HERE, "position_adjustments.json")
    overrides_per_setup = {}
    if os.path.exists(adj_path):
        with open(adj_path) as f:
            overrides_per_setup = json.load(f)

    # Shared spatial extents across all three rows.
    all_X = np.concatenate([DATA[n]["S11"]["X"] for n, _, _ in SETUPS])
    all_Y = np.concatenate([DATA[n]["S11"]["Y"] for n, _, _ in SETUPS])
    PAD = 0.4
    XLIM = (all_X.min() - PAD, all_X.max() + PAD)
    YLIM_INV = (all_Y.max() + PAD, all_Y.min() - PAD)  # inverted Y so row 1 is at top

    mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

    fig = plt.figure(figsize=(7.4, 10.5))
    gs = fig.add_gridspec(3, 2, wspace=0.02, hspace=0.10,
                          left=0.10, right=0.97, top=0.95, bottom=0.14)

    for ri, (name, title, kind) in enumerate(SETUPS):
        acc = ACC[name]
        overrides = overrides_per_setup.get(name, {})
        for ci, S in enumerate(SPARAMS):
            ax = fig.add_subplot(gs[ri, ci])
            d = DATA[name][S]
            X_shr, Y_shr = shrink_positions(d["labels"], d["X"], d["Y"])
            X = X_shr.copy(); Y = Y_shr.copy()
            for i, L in enumerate(d["labels"]):
                if L in overrides:
                    X[i], Y[i] = overrides[L][0], overrides[L][1]

            # Only show positions that have a real CNN accuracy entry.
            keep = np.array([L in acc for L in d["labels"]], dtype=bool)
            valid = keep & ~np.isnan(d["Z"])
            sizes = np.array([40 + 320 * float(np.clip(acc.get(L, 0.0), 0, 1))
                              for L in d["labels"]])

            ax.scatter(X[valid], Y[valid], c=d["Z"][valid],
                       cmap=CMAP, vmin=LIMS[S][0], vmax=LIMS[S][1],
                       s=sizes[valid], edgecolors="black", linewidths=0.3)
            draw_phantom_outline(ax, kind)
            draw_antennas(ax, XLIM, YLIM_INV, PAD)

            ax.set_aspect("equal")
            ax.set_xlim(XLIM); ax.set_ylim(YLIM_INV)
            ax.tick_params(axis="both", labelsize=7)
            if ci == 0:
                ax.set_ylabel(f"{title}\nY (in)", fontsize=10, labelpad=4)
            if ri == 2:
                ax.set_xlabel("X (in)", fontsize=9)
            if ri == 0:
                ax.set_title(f"|{S}|", fontsize=12, fontweight="bold", pad=4)

    # Shared colorbar at the bottom.
    cax = fig.add_axes([0.18, 0.045, 0.65, 0.015])
    sm = mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(*LIMS["S11"]), cmap=CMAP)
    cbar = fig.colorbar(sm, cax=cax, orientation="horizontal")
    cbar.set_label("Z(p) dB  -  dot size = CNN accuracy", fontsize=9)

    out_path = os.path.join(OUT_DIR, "paper_figure.png")
    fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()
