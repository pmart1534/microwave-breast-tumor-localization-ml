"""
detectable_difference_hunter.py
===============================
Hunter 4-port (A3 phantom) detectable-change, MAX-overlay edition.

Instead of separate reflection/transmission columns, this computes ONE map per
config: the "Max" overlay from detdifplot.py -- for each position, take the MAX
over all unique 4-port S-parameters (lower triangle Sij, i>=j -> 10 params) of
the band-mean linear CI-gap Delta, then convert to dB (20*log10).  Same DD math
as ../detectable_difference.py and Detectable Difference/detdifplot.py.

Per-config data:
  A3_Empty : the 1812 single session (today's antenna naming; the June18 LOSO
             empty data used a y-mirrored antenna naming, so its DD is not used
             here -- only its LOSO accuracy drives dot size in paper_figure_A3).
  A3_F4    : July03/A3_F4_SamMed (4 full sessions; partial 1703 dropped).
  A3_F5    : July03/A3_F5_SamMed (5 sessions).

Outputs into A3_hunter/results/:
  detectable_diff_<setup>.npz    rows_MAX = [(label,x,y,Z_dB,n), ...]
  detectable_diff_<setup>.csv
"""
from __future__ import annotations
import os, re, glob, json
import numpy as np
from scipy.stats import t as student_t

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_RES = os.path.join(HERE, "results")
os.makedirs(OUT_RES, exist_ok=True)

HUNTER = (r"C:\Users\peter\Desktop\EM Imaging\BreastPhantom\HunterVNA"
          r"\DataMeasurements\Sam Antennas\MediumAntenna\Separated")
EMPTY_1812 = os.path.join(
    HUNTER, "July03",
    "BreastPhantom_A3_FishingWeight_20260703_1812-20260704T004533Z-3-001",
    "BreastPhantom_A3_FishingWeight_20260703_1812")

SETUPS = {
    "A3_Empty": {"parent": EMPTY_1812, "sessions": None, "title": "A3 empty (1812)"},
    "A3_F4":    {"parent": os.path.join(HUNTER, "July03", "A3_F4_SamMed"),
                 "sessions": ["1623", "1642", "1707", "1726"], "title": "A3 + F4"},
    "A3_F5":    {"parent": os.path.join(HUNTER, "July03", "A3_F5_SamMed"),
                 "sessions": None, "title": "A3 + F5"},
}

# Unique lower-triangle S-parameters (i>=j) of the 4-port matrix.
UNIQUE_S = [(i, j) for j in range(1, 5) for i in range(1, 5) if i >= j]  # 10

def _mag_col(i, j):
    """CSV magnitude column for S_ij (recv i, stim j). Header order:
    Frequency, then for stim j=1..4: (S{i}-{j},P{i}-{j}) for recv i=1..4."""
    return 1 + ((j - 1) * 4 + (i - 1)) * 2

FREQ_LO_GHZ = 0.1
FREQ_HI_GHZ = 8.0
MIN_TRIALS_PER_POSITION = 16

CELL_IN, DIVIDER_IN, TOTAL_COLS = 1.0, 0.25, 6
_SPOFF = (CELL_IN / 2.0) - (DIVIDER_IN / 2.0)
_SUBOFF = {1: (-_SPOFF, -_SPOFF), 2: (+_SPOFF, -_SPOFF),
           3: (+_SPOFF, +_SPOFF), 4: (-_SPOFF, +_SPOFF)}
_RCP = re.compile(r"^(R\d+C\d+P\d+)_T\d+\.csv$", re.IGNORECASE)
_RCP_PARTS = re.compile(r"R(\d+)C(\d+)P(\d+)", re.IGNORECASE)


def rcp_to_xy(label):
    m = _RCP_PARTS.match(label)
    r, c, p = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ox, oy = _SUBOFF.get(p, (0.0, 0.0))
    return (c - 0.5) * CELL_IN + ox, (r - 0.5) * CELL_IN + oy


def read_csv_allS(path):
    """Return {(i,j): (F,) linear mag} for the 10 unique S-params, + freq_GHz."""
    try:
        raw = np.genfromtxt(path, delimiter=",", skip_header=1)
    except Exception:
        return None, None
    if raw.ndim != 2 or raw.shape[0] < 2:
        return None, None
    freq_GHz = raw[:, 0] / 1e9
    out = {}
    for (i, j) in UNIQUE_S:
        col = _mag_col(i, j)
        if col >= raw.shape[1]:
            return None, None
        out[(i, j)] = np.abs(raw[:, col].astype(np.float64))
    if not np.isfinite(np.concatenate(list(out.values()))).any():
        return None, None
    return out, freq_GHz


def list_sessions(parent, keep=None):
    # parent may itself be a session folder (CSVs directly inside)
    if glob.glob(os.path.join(parent, "R*C*P*_T*.csv")):
        return [(os.path.basename(parent), parent)]
    subs = []
    for name in sorted(os.listdir(parent)):
        p = os.path.join(parent, name)
        if not os.path.isdir(p) or not glob.glob(os.path.join(p, "R*C*P*_T*.csv")):
            continue
        if keep and not any(tok in name for tok in keep):
            continue
        subs.append((name, p))
    return subs


# ------------------- 95% CI helper (same math as A2 script) ----------------
def ci_from_linear(W):
    n = W.shape[1]
    mu = W.mean(axis=1); sd = W.std(axis=1, ddof=1)
    tc = student_t.ppf(0.975, n - 1)
    half = np.abs(tc * sd / np.sqrt(n))
    return np.abs(mu) - half, np.abs(mu) + half


def detectable_change_vec(B_lin, T_lin):
    bLo, bHi = ci_from_linear(B_lin)
    tLo, tHi = ci_from_linear(T_lin)
    ss = (bHi - bLo) + (tHi - tLo)
    d1 = tLo - bHi
    d2 = bLo - tHi
    Dv = np.zeros(B_lin.shape[0])
    pos = d1 >= 0
    neg = (~pos) & (np.abs(d1) >= ss)
    Dv[pos] = d1[pos]; Dv[neg] = d2[neg]
    return Dv


def pool_setup(parent, keep=None):
    sessions = list_sessions(parent, keep)
    if not sessions:
        raise FileNotFoundError(f"no sessions in {parent}")
    baseline = {ij: [] for ij in UNIQUE_S}
    by_label = {}
    freq_GHz = None
    for name, path in sessions:
        for bp in sorted(glob.glob(os.path.join(path, "baseline_T*.csv"))):
            mags, fq = read_csv_allS(bp)
            if mags is None:
                continue
            if freq_GHz is None:
                freq_GHz = fq
            for ij in UNIQUE_S:
                baseline[ij].append(mags[ij])
        for fp in sorted(glob.glob(os.path.join(path, "R*C*P*_T*.csv"))):
            m = _RCP.match(os.path.basename(fp))
            if not m:
                continue
            label = m.group(1).upper()
            mags, _ = read_csv_allS(fp)
            if mags is None:
                continue
            by_label.setdefault(label, {ij: [] for ij in UNIQUE_S})
            for ij in UNIQUE_S:
                by_label[label][ij].append(mags[ij])
    baseline = {ij: np.stack(v, axis=1) for ij, v in baseline.items()}   # (F,nB)
    for L in by_label:
        for ij in UNIQUE_S:
            by_label[L][ij] = np.stack(by_label[L][ij], axis=1)          # (F,nT)
    return dict(freq_GHz=freq_GHz, baseline=baseline, by_label=by_label,
                n_sessions=len(sessions), session_names=[n for n, _ in sessions])


def compute_maps(pool):
    """Return rows [(label,x,y,Z_maxAll_dB,n)] and the per-S-parameter band-mean
    linear Delta matrix avg_lin (nP, 10) aligned to UNIQUE_S, so downstream the
    MAX overlay can be recomputed for ANY antenna subset."""
    freq = pool["freq_GHz"]
    band = (freq >= FREQ_LO_GHZ) & (freq <= FREQ_HI_GHZ)
    rows, avg_lin = [], []
    for L, trials in pool["by_label"].items():
        n = trials[UNIQUE_S[0]].shape[1]
        if n < MIN_TRIALS_PER_POSITION:
            continue
        per_s = []
        for ij in UNIQUE_S:
            Dv = detectable_change_vec(pool["baseline"][ij], trials[ij])
            per_s.append(Dv[band].mean())             # band-mean linear Delta
        combined = max(per_s)                          # MAX over ALL S-params
        Z = 20.0 * np.log10(combined) if combined > 0 else np.nan
        x, y = rcp_to_xy(L)
        rows.append((L, x, y, Z, n))
        avg_lin.append(per_s)
    return rows, np.array(avg_lin, dtype=np.float64)


def write_csv(rows, out_path):
    with open(out_path, "w") as f:
        f.write("label,x_in,y_in,Z_MAX_dB,n\n")
        for L, x, y, Z, n in sorted(rows):
            zs = "NaN" if np.isnan(Z) else f"{Z:.4f}"
            f.write(f"{L},{x:.4f},{y:.4f},{zs},{int(n)}\n")


def main():
    summary = {}
    for name, cfg in SETUPS.items():
        print(f"\n=== {name} ({cfg['title']}) ===")
        pool = pool_setup(cfg["parent"], cfg["sessions"])
        print(f"  sessions: {pool['n_sessions']}  freq pts: {pool['freq_GHz'].shape[0]}  "
              f"baseline trials: {pool['baseline'][(1,1)].shape[1]}  "
              f"positions: {len(pool['by_label'])}")
        rows, avg_lin = compute_maps(pool)
        Z = np.array([r[3] for r in rows], float)
        print(f"  MAX-overlay Z (all S): {np.nanmin(Z):.1f} .. {np.nanmax(Z):.1f} dB "
              f"(median {np.nanmedian(Z):.1f}),  {np.sum(~np.isnan(Z))}/{len(rows)} detectable")
        write_csv(rows, os.path.join(OUT_RES, f"detectable_diff_{name}.csv"))
        np.savez_compressed(
            os.path.join(OUT_RES, f"detectable_diff_{name}.npz"),
            rows_MAX=np.array(rows, dtype=object),          # (label,x,y,Z_maxAll,n)
            avg_lin=avg_lin,                                # (nP, 10) linear Delta
            sparam_keys=np.array([f"S{i}{j}" for (i, j) in UNIQUE_S]),
            freq_GHz=pool["freq_GHz"], fmin=FREQ_LO_GHZ, fmax=FREQ_HI_GHZ,
        )
        summary[name] = dict(n_sessions=pool["n_sessions"], n_positions=len(rows),
                             baseline_trials=int(pool["baseline"][(1,1)].shape[1]))
    with open(os.path.join(OUT_RES, "detectable_diff_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote results to {OUT_RES}")


if __name__ == "__main__":
    main()
