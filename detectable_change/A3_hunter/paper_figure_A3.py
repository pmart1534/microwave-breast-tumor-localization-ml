"""
paper_figure_A3.py
==================
A3 (Hunter 4-port) detectable-change dot figure, antenna-mode consistent.

ONE antenna mode drives everything so the plot is internally consistent:
  - dot COLOR = MAX-overlay detectable change over ONLY that mode's S-parameters
  - dot SIZE  = that mode's LOSO accuracy (single-antenna / pair / full array)
  - antenna markers = only that mode's antennas

Modes:
  single1 -> antenna 1 only            -> DD uses S11;              markers {1}
  pair13  -> antennas 1 & 3            -> DD uses S11,S31,S33;      markers {1,3}
  all     -> full 4-port array         -> DD uses all 10 unique S;  markers {1,2,3,4}

Renders one figure per (mode, method):
  figures/paper_figure_A3_<mode>_<method>.png

Inputs: results/detectable_diff_A3_*.npz (avg_lin + sparam_keys),
        accuracy_data/per_position_accuracy_A3_*_<mode>__{cnn,mlp}.csv
Overlays: bowl + glandular outlines (traced), antenna positions
          (antenna_positions_A3.json), dot nudges (position_adjustments.json).
"""
from __future__ import annotations
import os, csv, re, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import Rectangle, Polygon, Ellipse

HERE = os.path.dirname(os.path.abspath(__file__))
RES_DIR = os.path.join(HERE, "results")
ACC_DIR = os.path.join(HERE, "accuracy_data")
OUT_DIR = os.path.join(HERE, "figures")
os.makedirs(OUT_DIR, exist_ok=True)

SETUPS = [
    ("A3_Empty", "A3 empty", "empty"),
    ("A3_F4",    "A3 + F4",   "F4"),
    ("A3_F5",    "A3 + F5",   "F5"),
]

# antenna mode -> ports used (DD S-params + accuracy + markers all follow this).
# refl=True restricts the DD to reflections Sii only (no transmission).
MODES = {
    "single1":     {"ports": [1],          "refl": False, "title": "antenna 1 (S11)"},
    "pair13":      {"ports": [1, 3],       "refl": False, "title": "antennas 1 & 3"},
    "all":         {"ports": [1, 2, 3, 4], "refl": False, "title": "all 4 antennas"},
    "refl_pair13": {"ports": [1, 3],       "refl": True,  "title": "antennas 1 & 3, reflection only"},
    "refl_all":    {"ports": [1, 2, 3, 4], "refl": True,  "title": "all 4 antennas, reflection only"},
}
RENDER_MODES = ["single1", "pair13", "all", "refl_pair13", "refl_all"]
METHODS = ["cnn", "mlp"]
CMAP = "jet"

# Built-in antenna positions (overridden by antenna_positions_A3.json).
ANTENNAS_DEFAULT = {1: (1.554, 4.237), 2: (1.539, 1.219),
                    3: (4.423, 1.428), 4: (4.543, 4.147)}

# ---- A3 OUTLINE CONSTANTS (from calibration/apply_calibration.py) ---------
BOWL_ELLIPSE_CENTER = (3.124, 3.028)
BOWL_ELLIPSE_RX     = 1.901
BOWL_ELLIPSE_RY     = 3.233
A3_F4_OUTLINE = [
    (1.86, 3.14), (1.72, 2.96), (1.63, 2.75), (1.50, 2.47),
    (1.50, 2.18), (1.61, 1.93), (1.79, 1.73), (2.05, 1.64),
    (2.39, 1.83), (2.62, 1.92), (2.81, 2.03), (2.98, 2.12),
    (3.14, 2.13), (3.28, 2.23), (3.40, 2.33), (3.50, 2.45),
    (3.59, 2.57), (3.64, 2.72), (3.69, 2.85), (3.85, 2.97),
    (3.92, 3.14), (4.01, 3.33), (4.09, 3.55), (4.17, 3.83),
    (4.09, 4.06), (3.90, 4.22), (3.70, 4.35), (3.44, 4.36),
    (3.25, 4.47), (3.02, 4.46), (2.81, 4.34), (2.64, 4.21),
    (2.53, 4.00), (2.47, 3.82), (2.40, 3.71), (2.33, 3.62),
    (2.26, 3.54), (2.21, 3.45), (2.13, 3.36), (2.01, 3.27),
]
A3_F5_OUTLINE = [
    (1.40, 3.43), (1.42, 3.14), (1.50, 2.87), (1.65, 2.62),
    (1.80, 2.39), (1.94, 2.14), (2.13, 1.92), (2.38, 1.77),
    (2.64, 1.61), (2.91, 1.42), (3.23, 1.33), (3.54, 1.46),
    (3.81, 1.64), (4.06, 1.81), (4.22, 2.07), (4.35, 2.31),
    (4.42, 2.56), (4.45, 2.81), (4.50, 3.02), (4.58, 3.22),
    (4.55, 3.43), (4.55, 3.64), (4.53, 3.85), (4.59, 4.12),
    (4.54, 4.38), (4.42, 4.62), (4.06, 4.57), (3.85, 4.65),
    (3.65, 4.72), (3.47, 4.95), (3.23, 5.27), (2.94, 5.25),
    (2.67, 5.15), (2.49, 4.88), (2.29, 4.72), (2.04, 4.62),
    (1.82, 4.46), (1.65, 4.23), (1.49, 3.99), (1.43, 3.71),
]


# --------------------------------------------------------------------------
def load_setup(name):
    npz = np.load(os.path.join(RES_DIR, f"detectable_diff_{name}.npz"), allow_pickle=True)
    rows = npz["rows_MAX"].tolist()
    return {
        "labels": [r[0] for r in rows],
        "X": np.array([r[1] for r in rows], float),
        "Y": np.array([r[2] for r in rows], float),
        "avg_lin": npz["avg_lin"],                    # (nP, 10) linear Delta
        "keys": [str(k) for k in npz["sparam_keys"]], # ["S11","S21",...]
    }


def dd_for_ports(d, ports, refl_only=False):
    """MAX-overlay Z(p) in dB over the S-parameters whose BOTH ports are in
    `ports` (unique lower-triangle Sij).  refl_only keeps only Sii."""
    ports = set(ports)
    cols = [i for i, k in enumerate(d["keys"])
            if int(k[1]) in ports and int(k[2]) in ports
            and (not refl_only or k[1] == k[2])]
    combined = d["avg_lin"][:, cols].max(axis=1)      # linear
    with np.errstate(divide="ignore"):
        return np.where(combined > 0, 20.0 * np.log10(combined), np.nan)


def load_accuracy(name, mode, method):
    path = os.path.join(ACC_DIR, f"per_position_accuracy_{name}_{mode}__{method}.csv")
    out = {}
    if not os.path.exists(path):
        print(f"[!] missing {path}")
        return out
    with open(path) as f:
        for row in csv.DictReader(f):
            try:
                out[row["label"]] = float(row["accuracy"])
            except (ValueError, KeyError):
                pass
    return out


def load_overrides():
    p = os.path.join(HERE, "position_adjustments.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def load_antennas(ports):
    pos = dict(ANTENNAS_DEFAULT)
    p = os.path.join(HERE, "antenna_positions_A3.json")
    if os.path.exists(p):
        for port, xy in json.load(open(p)).items():
            pos[int(port)] = (xy[0], xy[1])
    return [(k, pos[k][0], pos[k][1]) for k in sorted(pos) if k in ports]


SIGN = {1: (-1, -1), 2: (+1, -1), 3: (+1, +1), 4: (-1, +1)}
HALF_CELL, SHRINK = 0.375, 0.20


def shrink_positions(labels, X, Y):
    nX, nY = X.copy(), Y.copy()
    for i, L in enumerate(labels):
        m = re.match(r"R(\d+)C(\d+)P(\d+)", str(L))
        if not m:
            continue
        sx, sy = SIGN.get(int(m.group(3)), (0, 0))
        cx, cy = X[i] - sx * HALF_CELL, Y[i] - sy * HALF_CELL
        nX[i] = X[i] + SHRINK * (cx - X[i])
        nY[i] = Y[i] + SHRINK * (cy - Y[i])
    return nX, nY


def draw_antennas(ax, ants):
    w, h = 0.30, 0.55
    for num, x, y in ants:
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor="0.15",
                               edgecolor="k", zorder=5, clip_on=False))
        ax.text(x, y, str(num), ha="center", va="center", color="w",
                fontsize=8, fontweight="bold", zorder=6, clip_on=False)


def draw_outline(ax, kind, color="0.1", lw=1.3):
    ax.add_patch(Ellipse(BOWL_ELLIPSE_CENTER, 2 * BOWL_ELLIPSE_RX,
                         2 * BOWL_ELLIPSE_RY, fill=False, edgecolor=color, lw=lw))
    pts = {"F4": A3_F4_OUTLINE, "F5": A3_F5_OUTLINE}.get(kind)
    if pts:
        ax.add_patch(Polygon(pts, closed=True, fill=False, edgecolor=color,
                             lw=lw, linestyle=(0, (4, 2))))


def render(mode, method, orient="v"):
    """orient='v' -> 3 stacked panels (portrait, for the paper);
       orient='h' -> 1x3 side-by-side panels (landscape, for slides)."""
    ports = MODES[mode]["ports"]
    refl = MODES[mode].get("refl", False)
    DATA = {n: load_setup(n) for n, _, _ in SETUPS}
    Zmap = {n: dd_for_ports(DATA[n], ports, refl) for n, _, _ in SETUPS}
    ACC = {n: load_accuracy(n, mode, method) for n, _, _ in SETUPS}
    if all(len(ACC[n]) == 0 for n, _, _ in SETUPS):
        print(f"skip {mode}/{method}/{orient}: no matched accuracy CSVs yet")
        return
    OVR = load_overrides()
    ants = load_antennas(ports)

    # shared colour scale = 2..98 pct of this mode's Z across all configs
    allZ = np.concatenate([Zmap[n] for n, _, _ in SETUPS])
    allZ = allZ[~np.isnan(allZ)]
    vmin, vmax = np.percentile(allZ, [2, 98])
    vmin = np.floor(vmin / 5) * 5; vmax = np.ceil(vmax / 5) * 5

    ant_x = [xy[0] for xy in ANTENNAS_DEFAULT.values()]
    ant_y = [xy[1] for xy in ANTENNAS_DEFAULT.values()]
    all_X = np.concatenate([DATA[n]["X"] for n, _, _ in SETUPS])
    all_Y = np.concatenate([DATA[n]["Y"] for n, _, _ in SETUPS])
    PAD = 0.5
    XLIM = (min(all_X.min(), min(ant_x)) - PAD, max(all_X.max(), max(ant_x)) + PAD)
    YLIM = (max(all_Y.max(), max(ant_y)) + PAD, min(all_Y.min(), min(ant_y)) - PAD)

    mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    if orient == "h":
        fig = plt.figure(figsize=(12.6, 4.9))
        gs = fig.add_gridspec(1, 3, wspace=0.06, left=0.045, right=0.895,
                              top=0.84, bottom=0.10)
    else:
        fig = plt.figure(figsize=(4.7, 11.0))
        gs = fig.add_gridspec(3, 1, hspace=0.14, left=0.16, right=0.86,
                              top=0.93, bottom=0.10)

    for ri, (name, title, kind) in enumerate(SETUPS):
        ax = fig.add_subplot(gs[0, ri] if orient == "h" else gs[ri, 0])
        d = DATA[name]; acc = ACC[name]; Z = Zmap[name]
        X, Y = shrink_positions(d["labels"], d["X"], d["Y"])
        ov = OVR.get(name, {})
        for i, L in enumerate(d["labels"]):
            if L in ov:
                X[i], Y[i] = ov[L][0], ov[L][1]
        keep = np.array([L in acc for L in d["labels"]])
        valid = keep & ~np.isnan(Z)
        sizes = np.array([50 + 340 * float(np.clip(acc.get(L, 0.0), 0, 1))
                          for L in d["labels"]])
        ax.scatter(X[valid], Y[valid], c=Z[valid], cmap=CMAP, vmin=vmin, vmax=vmax,
                   s=sizes[valid], edgecolors="black", linewidths=0.4, zorder=3)
        draw_outline(ax, kind)
        draw_antennas(ax, ants)
        ax.set_aspect("equal")
        ax.set_xlim(XLIM); ax.set_ylim(YLIM)
        ax.tick_params(labelsize=7)
        if orient == "h":
            ax.set_title(title, fontsize=12, fontweight="bold")
            ax.set_xlabel("X (in)", fontsize=9)
            if ri == 0:
                ax.set_ylabel("Y (in)", fontsize=10)
            else:
                ax.set_yticklabels([])
        else:
            ax.set_ylabel(f"{title}\nY (in)", fontsize=10)
            if ri == len(SETUPS) - 1:
                ax.set_xlabel("X (in)", fontsize=9)

    dd_label = {"single1": "S11", "pair13": "max S11/S31/S33",
                "all": "max over all S", "refl_pair13": "max S11/S33",
                "refl_all": "max S11/S22/S33/S44"}.get(mode, "DD")
    sm = mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(vmin, vmax), cmap=CMAP)
    if orient == "h":
        cax = fig.add_axes([0.912, 0.12, 0.014, 0.68])
        cb = fig.colorbar(sm, cax=cax, orientation="vertical")
        cb.set_label(f"{dd_label} Z(p) dB", fontsize=9)
        cb.ax.tick_params(labelsize=8)
        fig.suptitle(f"Detectable change (color, {dd_label})  vs  {method.upper()} "
                     f"LOSO accuracy (dot size)  --  {MODES[mode]['title']}",
                     fontsize=12.5, fontweight="bold")
    else:
        cax = fig.add_axes([0.16, 0.045, 0.70, 0.013])
        cb = fig.colorbar(sm, cax=cax, orientation="horizontal")
        cb.set_label(f"{dd_label} Z(p) dB (color)  -  dot size = {method.upper()} "
                     f"{MODES[mode]['title']} LOSO acc", fontsize=8)
        fig.suptitle(f"A3 detectable change [{MODES[mode]['title']}]\nvs {method.upper()} accuracy",
                     fontsize=12, fontweight="bold")

    suffix = ("_h" if orient == "h" else "") + os.environ.get("A3_FIG_SUFFIX", "")
    out = os.path.join(OUT_DIR, f"paper_figure_A3_{mode}_{method}{suffix}.png")
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {os.path.basename(out)}")


def main():
    for mode in RENDER_MODES:
        for method in METHODS:
            for orient in ("v", "h"):
                render(mode, method, orient)


if __name__ == "__main__":
    main()
