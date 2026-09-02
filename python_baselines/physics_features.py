"""Physics-aware features for cross-session A2_Empty.

Inspired by Above-80's 2538-D pipeline but reorganised for variety:
  - magnitude & phase of each (calibrated) S-param
  - per-trace mean/std
  - S12 / S21 reciprocity residual (|S12 - S21|)
  - IFFT envelope of each S-param (first 64 time bins) — physical TDR proxy
  - inter-trace ratios |S11|/|S21|, |S22|/|S12|

All features are per-trial. Calibration must be done upstream (subtract baseline).
Output: dict with X_phys (N, F_phys) float32, feature names, etc.
"""
from __future__ import annotations
import numpy as np


def physics_features_from_complex(Xc_cal: np.ndarray, n_time_bins: int = 64):
    """Xc_cal: (N, 4, F) calibrated complex S-params.  Returns (N, D)."""
    N, _, F = Xc_cal.shape
    feats = []
    names = []

    mag = np.abs(Xc_cal).astype(np.float32)              # (N, 4, F)
    ph  = np.angle(Xc_cal).astype(np.float32)
    re  = np.real(Xc_cal).astype(np.float32)
    im  = np.imag(Xc_cal).astype(np.float32)

    for k, sp in enumerate(["S11", "S12", "S22", "S21"]):
        # raw mag/phase/Re/Im
        for arr, suf in [(mag[:, k], "mag"), (ph[:, k], "ph"),
                         (re[:, k], "re"), (im[:, k], "im")]:
            feats.append(arr)
            names += [f"{sp}_{suf}_f{j}" for j in range(F)]
        # per-trace stats
        for stat_fn, suf in [(np.mean, "mean"), (np.std, "std"),
                             (np.median, "med"), (np.max, "max"), (np.min, "min")]:
            v = stat_fn(mag[:, k], axis=1, keepdims=True)
            feats.append(v.astype(np.float32))
            names.append(f"{sp}_mag_{suf}")
        # IFFT envelope
        td = np.fft.ifft(Xc_cal[:, k, :], axis=-1).astype(np.complex64)
        env = np.abs(td[:, :n_time_bins]).astype(np.float32)
        feats.append(env)
        names += [f"{sp}_ifft{j}" for j in range(n_time_bins)]

    # reciprocity residual (S12 vs S21)
    rec_mag = np.abs(Xc_cal[:, 1, :] - Xc_cal[:, 3, :]).astype(np.float32)
    feats.append(rec_mag); names += [f"rec_mag_f{j}" for j in range(F)]
    rec_ph  = np.angle(Xc_cal[:, 1, :] / (Xc_cal[:, 3, :] + 1e-9)).astype(np.float32)
    feats.append(rec_ph);  names += [f"rec_ph_f{j}" for j in range(F)]

    # inter-trace ratios (log-scale to compress)
    eps = 1e-8
    r1 = np.log10(mag[:, 0] + eps) - np.log10(mag[:, 3] + eps)  # |S11|/|S21|
    r2 = np.log10(mag[:, 2] + eps) - np.log10(mag[:, 1] + eps)  # |S22|/|S12|
    feats += [r1.astype(np.float32), r2.astype(np.float32)]
    names += [f"r_S11_S21_f{j}" for j in range(F)] + [f"r_S22_S12_f{j}" for j in range(F)]

    # Concatenate along feature axis
    flat = []
    for f in feats:
        if f.ndim == 1:
            flat.append(f.reshape(-1, 1))
        else:
            flat.append(f)
    X = np.concatenate(flat, axis=1).astype(np.float32)
    return X, names


def build_physics_dataset(sessions, mode="sub_combo"):
    """Calibrate each session, compute physics features, concatenate."""
    from data import build_dataset, _rows_to_complex
    # We need calibrated COMPLEX features, not the 8-ch real, so do calibration here:
    sids = sorted(sessions.keys())
    pos_sets = [set(int(p) for p in sessions[s]["y_pos"]) for s in sids]
    valid = sorted(pos_sets[0].intersection(*pos_sets[1:]))
    pos_to_label = {p: i for i, p in enumerate(valid)}

    Xs, ys, ss, ps = [], [], [], []
    for si, sid in enumerate(sids):
        S = sessions[sid]
        Xc = S["Xc"]; base = S["base_c"]
        if mode == "sub":
            Y = Xc - base[None, :, :]
        elif mode == "sub_combo":
            Y = Xc - base[None, :, :]
            Y = Y - Y.mean(axis=0, keepdims=True)
        elif mode == "none":
            Y = Xc
        else:
            raise ValueError(mode)
        keep = np.array([(int(p) in pos_to_label) for p in S["y_pos"]], dtype=bool)
        Y = Y[keep]
        Xphys, names = physics_features_from_complex(Y)
        ys.append(np.array([pos_to_label[int(p)] for p in S["y_pos"][keep]], dtype=np.int64))
        Xs.append(Xphys)
        ss.append(np.full(Y.shape[0], si, dtype=np.int64))
        ps.append(S["y_pos"][keep].astype(np.int64))
    X = np.concatenate(Xs, axis=0)
    y = np.concatenate(ys, axis=0)
    sess = np.concatenate(ss, axis=0)
    pos = np.concatenate(ps, axis=0)
    print(f"[physics] X={X.shape}  K={len(valid)}  sessions={len(sids)}  n_feats={X.shape[1]}")
    return dict(X=X, y=y, sess=sess, pos=pos, num_classes=len(valid),
                num_sessions=len(sids), sids=sids, feature_names=names,
                label_to_pos=valid)


if __name__ == "__main__":
    import data as data_mod
    sessions = data_mod.load_all_sessions()
    D = build_physics_dataset(sessions, mode="sub_combo")
    print("OK:", D["X"].shape, "min/max:", D["X"].min(), D["X"].max())
