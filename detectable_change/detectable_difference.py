"""
detectable_difference.py  (Research Paper edition)
==================================================
Adapted from Above 95 Percent/paper/detectable_difference.py.

Differences from the original:
  - Points at the THREE April-2026 phantom configurations actually used in
    the J-ERM paper (A2 empty, A2+F4, A2+F5), all under
    C:\\Users\\peter\\Desktop\\EM Imaging\\BreastPhantom\\.
  - Pools both repeats of the A2 empty session and both Manitoba-antenna
    sessions of A2+F5.
  - Uses |S11| and |S12| (matches the caption in the paper). For a reciprocal
    network |S12| = |S21|, so this is equivalent to the original script's
    S21 choice; the column heading just says S12 to match how it is reported
    in the manuscript.
  - Lowers MIN_TRIALS_PER_POSITION to 16 because the A2+F4 configuration
    only has a single April session available.
  - Writes outputs into the Research Paper/Detectable Difference subtree so
    the original Above 95 Percent results are not overwritten.
  - Also generates a single 3-row x 2-col panel figure into figures/. For
    the full paper figure with phantom outlines and CNN-accuracy dot sizes,
    run brainstorm_variations.py after this script.

All CI math is unchanged: same 95% CI gap formula, same dB conversion.
"""
from __future__ import annotations
import os, re, glob, json
import numpy as np
import scipy.io as sio
from scipy.stats import t as student_t
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import Rectangle

# ----------------------------- Paths -----------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
# Datasets live in <repo>/datasets/, one folder per phantom configuration.
PHANTOM_BASE = os.path.abspath(os.path.join(_HERE, os.pardir, "datasets"))

# Each entry is a list of explicit filenames so we don't accidentally pick up
# unrelated sessions sitting in the same parent folder.
SETUPS = {
    "A2_Empty": {
        "files": [
            os.path.join(PHANTOM_BASE, "A2_Empty",
                "Imager_BreastPhantom_A2_NoGland_InitialBreastAntenna_MetalMarble_64Pos_16Trials_20260411_1524.mat"),
            os.path.join(PHANTOM_BASE, "A2_Empty",
                "Imager_BreastPhantom_A2_NoGland_InitialBreastAntenna_MetalMarble_64Pos_16Trials_20260411_1550.mat"),
        ],
        "title": "Empty A2",
    },
    "A2_F4": {
        "files": [
            os.path.join(PHANTOM_BASE, "A2_F4",
                "FIXEDImager_BreastPhantom_A2_Gland_F4_OriginalBreastAntenna_MetalMarble_64Pos_16Trials_20260411_1917.mat"),
        ],
        "title": "A2 + F4 glandular",
        # Single position sitting directly in front of the left antenna at
        # (1.125, 3.125). Its Z value is dominated by direct coupling rather
        # than the marble's perturbation, so it skews the color scale.
        "exclude_positions": {"R4C2P1"},
    },
    "A2_F5": {
        "files": [
            os.path.join(PHANTOM_BASE, "A2_F5",
                "Imager_BreastPhantom_A2_Gland_F5_ManetobaAntenna_MetalMarble_64Pos_16Trials_20260413_1118.mat"),
            os.path.join(PHANTOM_BASE, "A2_F5",
                "Imager_BreastPhantom_A2_Gland_F5_ManetobaAntenna_MetalMarble_64Pos_28Trials_20260413_1157.mat"),
        ],
        "title": "A2 + F5 glandular",
    },
}

# Aggregate Delta(f) over the full measured VNA sweep, dropping only the
# extreme low edge (0.3 MHz) which sits far below the antenna's usable band.
# Effective range: 1 MHz to 6.5 GHz (200 of the 201 points).
FREQ_LO_GHZ = 0.001
FREQ_HI_GHZ = 6.5

# S-parameters reported in the paper figure.
SPARAMS = ("S11", "S12")

# Drop positions that never accumulated this many pooled trials. Lowered from
# 32 to 16 because A2+F4 only has one April session (16 trials per position).
MIN_TRIALS_PER_POSITION = 16

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_FIGS = os.path.join(HERE, "figures")
OUT_RES  = os.path.join(HERE, "results")
os.makedirs(OUT_FIGS, exist_ok=True)
os.makedirs(OUT_RES, exist_ok=True)

# Shared dB scale across the three rows of the panel so they are directly
# comparable. The values are taken from the .npz outputs after a first run;
# adjust here if a new dataset shifts the range noticeably.
COLOR_LIMS = {
    "S11": (-90, -25),
    "S12": (-90, -25),
}

# ------------------------- File loading --------------------------------------

def load_session(path):
    d = sio.loadmat(path, squeeze_me=True, struct_as_record=False)
    data        = d["data"]
    baselineAll = d["baselineAll"]
    freq_Hz     = d["freq"].astype(np.float64)
    posLabels   = d["posLabels"]
    skipped     = np.array(d["skippedPositions"]).astype(bool)
    xyCoords    = d["xyCoords"].astype(np.float64)
    trialCount  = int(d["trialCount"])
    traceList   = d["traceList"]

    s_row = {}
    for i in range(traceList.shape[0]):
        name = str(traceList[i, 1]).strip().upper()
        s_row[name] = 2 * i

    return dict(
        path=path, data=data, baselineAll=baselineAll, freq_Hz=freq_Hz,
        posLabels=posLabels, skipped=skipped, xy=xyCoords,
        trialCount=trialCount, s_row=s_row,
    )

# --------------------- 95% CI helper -----------------------------------------

def ci_from_linear(W):
    """W: (numFreq, nTrials) linear magnitudes."""
    n = W.shape[1]
    mu = W.mean(axis=1)
    sd = W.std(axis=1, ddof=1)
    tc = student_t.ppf(0.975, n - 1)
    half = np.abs(tc * sd / np.sqrt(n))
    return np.abs(mu) - half, np.abs(mu) + half

def detectable_change_vec(B_lin, T_lin):
    """Same CI-gap formula as Mouad's AheatMap.m."""
    F = B_lin.shape[0]
    bLo, bHi = ci_from_linear(B_lin)
    tLo, tHi = ci_from_linear(T_lin)
    bW = bHi - bLo
    tW = tHi - tLo
    d1 = tLo - bHi
    d2 = bLo - tHi
    Dv = np.zeros(F, dtype=np.float64)
    pos = d1 >= 0
    neg = (~pos) & (np.abs(d1) >= (bW + tW))
    Dv[pos] = d1[pos]
    Dv[neg] = d2[neg]
    return Dv

# --------------------- Pool sessions -----------------------------------------

def pool_setup(paths, exclude_positions=None):
    if not paths:
        raise FileNotFoundError("No matching .mat files for setup")
    exclude_positions = set(exclude_positions or [])
    first = load_session(paths[0])
    freq_GHz = first["freq_Hz"] / 1e9
    F = freq_GHz.shape[0]

    baseline = {s: [] for s in SPARAMS}
    by_label = {}

    for p in paths:
        sess = load_session(p)
        for s in SPARAMS:
            ridx = sess["s_row"][s]
            B_dB = sess["baselineAll"][ridx, :, :]
            if B_dB.ndim == 1:
                B_dB = B_dB[:, None]
            baseline[s].append(10.0 ** (B_dB / 20.0))
        for pi, label in enumerate(sess["posLabels"]):
            label = str(label)
            if sess["skipped"][pi]:
                continue
            if label in exclude_positions:
                continue
            xy = sess["xy"][pi].tolist()
            if label not in by_label:
                by_label[label] = dict(xy=xy, trials={s: [] for s in SPARAMS})
            for s in SPARAMS:
                ridx = sess["s_row"][s]
                for t in range(1, sess["trialCount"] + 1):
                    trial = sess["data"][pi, t]
                    if trial is None or (isinstance(trial, np.ndarray) and trial.size == 0):
                        continue
                    if np.any(np.isnan(trial)):
                        continue
                    by_label[label]["trials"][s].append(
                        10.0 ** (np.asarray(trial[ridx, :]) / 20.0)
                    )

    baseline = {s: np.concatenate(baseline[s], axis=1) for s in SPARAMS}
    for L in list(by_label.keys()):
        for s in SPARAMS:
            if len(by_label[L]["trials"][s]) > 0:
                by_label[L]["trials"][s] = np.stack(by_label[L]["trials"][s], axis=1)
            else:
                by_label[L]["trials"][s] = np.empty((F, 0))

    return dict(freq_GHz=freq_GHz, baseline=baseline, by_label=by_label)

# --------------------- Detectable change map ---------------------------------

def compute_Z_map(pool, fmin=FREQ_LO_GHZ, fmax=FREQ_HI_GHZ,
                  min_trials=MIN_TRIALS_PER_POSITION):
    freq_GHz = pool["freq_GHz"]
    band = (freq_GHz >= fmin) & (freq_GHz <= fmax)
    out = {}
    dropped = set()
    for s in SPARAMS:
        B = pool["baseline"][s]
        rows = []
        for L, info in pool["by_label"].items():
            T = info["trials"][s]
            if T.shape[1] < min_trials:
                dropped.add(L)
                continue
            Dv = detectable_change_vec(B, T)
            avg = Dv[band].mean()
            if avg > 0:
                Z = 20.0 * np.log10(avg)
            else:
                Z = np.nan
            rows.append((L, info["xy"][0], info["xy"][1], Z, T.shape[1]))
        out[s] = rows
    if dropped:
        print(f"  dropped {len(dropped)} position(s) below min_trials")
    return out

# --------------------- 3-row x 2-col panel figure ----------------------------

def fig_dd_panel(npz_paths, out_path):
    """Assemble the publication figure.

    Rows: A2_Empty (top), A2_F4 (middle), A2_F5 (bottom).
    Cols: |S11| (left), |S12| (right).
    Color scale is shared across the three rows within each column so the
    configurations are directly comparable.
    """
    mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    setups = [
        ("A2_Empty", "Empty A2"),
        ("A2_F4",    "A2 + F4"),
        ("A2_F5",    "A2 + F5"),
    ]
    panel_letters = [["(a)", "(b)"], ["(c)", "(d)"], ["(e)", "(f)"]]

    # First pass: figure out shared X/Y extents across all three configurations
    # so every panel is on the same scale and the dots are the same physical
    # size from row to row.
    all_X = []
    all_Y = []
    for setup, _ in setups:
        npz = np.load(npz_paths[setup], allow_pickle=True)
        for S in SPARAMS:
            rows = npz[f"rows_{S}"].tolist()
            all_X.extend(r[1] for r in rows)
            all_Y.extend(r[2] for r in rows)
    all_X = np.asarray(all_X, dtype=float)
    all_Y = np.asarray(all_Y, dtype=float)
    pad = 0.5
    XLIM = (all_X.min() - pad, all_X.max() + pad)
    YLIM = (all_Y.max() + pad, all_Y.min() - pad)   # inverted
    # Antenna face positions are taken from the FULL extent so they sit at the
    # outermost X positions regardless of which configuration is plotted.
    xL_global = all_X.min()
    xR_global = all_X.max()
    yC_global = (all_Y.min() + all_Y.max()) / 2.0

    fig, axes = plt.subplots(3, 2, figsize=(5.0, 7.9))
    fig.patch.set_facecolor("white")

    for ri, (setup, title) in enumerate(setups):
        npz = np.load(npz_paths[setup], allow_pickle=True)
        for ci, S in enumerate(SPARAMS):
            ax = axes[ri][ci]
            ax.set_facecolor("white")
            rows = npz[f"rows_{S}"].tolist()
            X = np.array([r[1] for r in rows], dtype=float)
            Y = np.array([r[2] for r in rows], dtype=float)
            Z = np.array([r[3] for r in rows], dtype=float)
            valid = ~np.isnan(Z)
            lims = COLOR_LIMS[S]
            if (~valid).any():
                ax.scatter(X[~valid], Y[~valid],
                           c=[(0.82, 0.82, 0.82)], s=70, edgecolors="none")
            sc = ax.scatter(X[valid], Y[valid], c=Z[valid], cmap="jet",
                            vmin=lims[0], vmax=lims[1],
                            s=100, edgecolors="black", linewidths=0.3)
            ax.set_aspect("equal")
            ax.set_xlim(XLIM); ax.set_ylim(YLIM)
            if ri == 2:
                ax.set_xlabel("X (in)")
            if ci == 0:
                ax.set_ylabel(f"{title}\nY (in)", fontsize=9)
            cbar = plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
            cbar.ax.tick_params(labelsize=7)
            cbar.set_label(f"|{S}| Z(p) (dB)", fontsize=8)
            ax.tick_params(labelsize=7)
            # Panel letter placed BELOW the axes so it can't overlap any dot.
            # Bottom row goes farther down so it doesn't overlap the X label.
            letter_y = -0.36 if ri == 2 else -0.22
            ax.text(0.5, letter_y, panel_letters[ri][ci],
                    transform=ax.transAxes, va="top", ha="center",
                    fontsize=10, fontweight="bold")
            # Antennas at the global left/right faces
            for xface, sign in [(xL_global, -1), (xR_global, +1)]:
                x0 = xface + sign * 0.08
                x1 = xface + sign * 0.45
                rect = Rectangle((min(x0, x1), yC_global - 0.55),
                                  abs(x1 - x0), 1.1,
                                  facecolor="black", edgecolor="black")
                ax.add_patch(rect)
    plt.tight_layout(h_pad=-3.0)
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

# --------------------- Driver ------------------------------------------------

def write_csv(rows_per_S, out_path):
    all_labels = sorted({r[0] for s_rows in rows_per_S.values() for r in s_rows})
    lookup = {s: {r[0]: r for r in rows_per_S[s]} for s in rows_per_S}
    with open(out_path, "w") as f:
        cols = ",".join(f"Z_{s}_dB" for s in SPARAMS)
        ncols = ",".join(f"n_{s}" for s in SPARAMS)
        f.write(f"label,x_in,y_in,{cols},{ncols}\n")
        for L in all_labels:
            xy = None
            zS = {s: "" for s in SPARAMS}
            nS = {s: "" for s in SPARAMS}
            for s in SPARAMS:
                if L in lookup[s]:
                    _, x, y, Z, n = lookup[s][L]
                    xy = (x, y)
                    zS[s] = f"{Z:.4f}" if not np.isnan(Z) else "NaN"
                    nS[s] = str(int(n))
            if xy is None:
                continue
            zvals = ",".join(zS[s] for s in SPARAMS)
            nvals = ",".join(nS[s] for s in SPARAMS)
            f.write(f"{L},{xy[0]:.4f},{xy[1]:.4f},{zvals},{nvals}\n")

def main():
    summary = {}
    npz_paths = {}
    for setup_name, cfg in SETUPS.items():
        print(f"\n=== {setup_name} ===")
        files = [f for f in cfg["files"] if os.path.exists(f)]
        for f in cfg["files"]:
            mark = "OK" if os.path.exists(f) else "MISSING"
            print(f"  [{mark}] {os.path.basename(f)}")
        excl = cfg.get("exclude_positions", set())
        if excl:
            print(f"  excluding {len(excl)} near-antenna position(s): {sorted(excl)}")
        pool = pool_setup(files, exclude_positions=excl)
        print(f"  freq points: {pool['freq_GHz'].shape[0]},"
              f" baselines pooled per S: {pool['baseline']['S11'].shape[1]}")
        print(f"  positions with object trials: {len(pool['by_label'])}")
        rows_per_S = compute_Z_map(pool)
        for s in SPARAMS:
            valid = sum(1 for r in rows_per_S[s] if not np.isnan(r[3]))
            print(f"    {s}: {valid}/{len(rows_per_S[s])} detectable")
        write_csv(rows_per_S, os.path.join(OUT_RES, f"detectable_diff_{setup_name}.csv"))
        npz_path = os.path.join(OUT_RES, f"detectable_diff_{setup_name}.npz")
        np.savez_compressed(
            npz_path,
            **{f"rows_{s}": np.array(rows_per_S[s], dtype=object) for s in SPARAMS},
            freq_GHz=pool["freq_GHz"],
            fmin=FREQ_LO_GHZ, fmax=FREQ_HI_GHZ,
        )
        npz_paths[setup_name] = npz_path
        summary[setup_name] = {
            "n_files": len(files),
            "n_pos_with_object_trials": len(pool["by_label"]),
            "baseline_trials_pooled": pool["baseline"]["S11"].shape[1],
        }

    # Single composite panel figure (basic 3x2 layout, no outlines or dot sizing).
    # For the full paper figure with phantom outlines and CNN-accuracy dot sizes,
    # run brainstorm_variations.py after this script.
    panel_path = os.path.join(OUT_FIGS, "fig_dd_panel.png")
    fig_dd_panel(npz_paths, panel_path)
    print(f"\nWrote panel figure: {panel_path}")

    with open(os.path.join(OUT_RES, "detectable_diff_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
