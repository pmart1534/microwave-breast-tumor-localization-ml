r"""MLP Leave-One-Session-Out driver -- the head-to-head counterpart to
../cnn_matlab/Imager_CNN_LOSO.m.

Runs the SAME MLP METHOD proven in Above 95 Percent
(test_hunter_sam_med_june18.py):

    per-session baseline calibration
    -> physics features
    -> per-session z-score (the cross-session "KEY" trick)
    -> 3-seed MLP(256,128) ensemble  [+ LogReg]
    -> per-position majority vote

on the SAME Hunter 4-port sessions the CNN sees, with the SAME antenna
subset options so the two methods are directly comparable:

    all    : 16 S-params (physics_features_4port,     ~17.6k-D)
    pair   :  2 antennas (physics_features_from_complex, 4-channel 4296-D)
             e.g. ports 1&3 -> S11,S13,S31,S33 mapped to [S11,S12,S22,S21]
    single :  1 antenna  (physics_features_1channel,  873-D)  e.g. antenna 1 -> S11

Usage (from this folder, using the Above 95 Percent venv):
    ..\..\"Above 95 Percent"\venv\Scripts\python.exe run_mlp_loso.py ^
        --setup "C:\...\Separated\June18" ^
        --antenna all
    --antenna choices:  all | pair:1,3 | pair:2,4 | single:1 | single:2 ...

Outputs (mirrors the CNN's json layout so results sit side by side):
    ../results/mlp_loso_<tag>.json
"""
from __future__ import annotations
import os, sys, json, argparse, time
from collections import defaultdict
from pathlib import Path
import numpy as np

# --- make the Above 95 Percent code importable (loader + feature builders) ---
ABOVE95_CODE = Path(r"C:\Users\peter\Desktop\EM Imaging\Above 95 Percent\code")
sys.path.insert(0, str(ABOVE95_CODE))

from hunter_loader import load_hunter_session                     # noqa: E402
from physics_features_4port import physics_features_4port         # noqa: E402
from physics_features import physics_features_from_complex        # noqa: E402
from physics_features_1channel import physics_features_1channel   # noqa: E402
from data import per_session_zscore                               # noqa: E402
from sklearn.preprocessing import StandardScaler                  # noqa: E402
from sklearn.neural_network import MLPClassifier                  # noqa: E402
from sklearn.linear_model import LogisticRegression              # noqa: E402
from joblib import Parallel, delayed                              # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

ENSEMBLE_SEEDS = (42, 7, 13)

# Hunter NATIVE frequency grid (0.1-8 GHz, 791 pts) -- use this instead of the
# legacy 201-pt/0.3-6.5 GHz grid so the MLP sees the same data as the CNN.
NATIVE_FREQ = np.linspace(0.1e9, 8.0e9, 791)
N_TDR_BINS = 64
TOTAL_COLS = 6      # grid columns, for pos-id <-> (row,col) and quadrant split

# full16 row layout (hunter_loader): S_{ij} at row (i-1)*4 + (j-1), i=from, j=to.
def _full16_row(i, j):
    return (i - 1) * 4 + (j - 1)


# ---------------------------------------------------------------------------
def list_sessions(parent: Path, only=None):
    """Return [(name, path), ...] for Hunter session subfolders under parent.

    If `only` (list of name substrings) is given, keep only sessions whose
    folder name contains one of the substrings -- e.g. ["1432","1454","1516"].
    """
    sessions = []
    for p in sorted(parent.iterdir()):
        if p.is_dir() and (list(p.glob("R*C*P*_T*.csv")) or (p / "session_metadata.txt").exists()):
            if only and not any(tok in p.name for tok in only):
                continue
            sessions.append((p.name, p))
    return sessions


def parse_antenna(spec: str):
    """'all' | 'pair:1,3' | 'single:2' | 'refl:1,2,3,4' | 'refl:1,3'
    -> (mode, ports_tuple).  'refl' = REFLECTION-ONLY (Sii), no transmission."""
    spec = spec.strip().lower()
    if spec in ("all", "4", "16"):
        return "all", (1, 2, 3, 4)
    if spec.startswith("refl"):
        ports = tuple(sorted(int(x) for x in spec.split(":")[1].replace(" ", "").split(",")))
        return "refl", ports
    if spec.startswith("pair"):
        ports = tuple(int(x) for x in spec.split(":")[1].replace(" ", "").split(","))
        assert len(ports) == 2, "pair needs exactly two ports, e.g. pair:1,3"
        return "pair", tuple(sorted(ports))
    if spec.startswith("single"):
        p = int(spec.split(":")[1])
        return "single", (p,)
    raise ValueError(f"bad --antenna {spec!r}")


def _remap_perm(remap):
    """remap[a-1] = OLD port that becomes NEW port a. Returns a length-16
    permutation of the full16 rows so new S(a,b) <- old S(remap[a],remap[b])."""
    perm = np.empty(16, dtype=int)
    for a in range(1, 5):
        for b in range(1, 5):
            perm[_full16_row(a, b)] = _full16_row(remap[a - 1], remap[b - 1])
    return perm


def load_session(path: Path, mode, ports, remap=None):
    """Load one Hunter session in full16, subset to the chosen antennas.

    Returns per_pos {pos_idx: (n, C, F) complex}, base_c (C, F), pos_xy.
    C depends on mode: all->16, pair->4 (as [S11,S12,S22,S21]), single->1.

    remap: optional list [old_for_new1, ...] to relabel antenna ports (e.g.
    [2,1,4,3] to bring June18's naming into today's convention) BEFORE subsetting.
    """
    out = load_hunter_session(str(path), freq_target=NATIVE_FREQ, mode="full16")
    Xc16, base16 = out["Xc"], out["base_c"]     # (N,16,F), (16,F)  F=791 native
    ypos, xy = out["y_pos"], out["xy"]
    if remap:
        perm = _remap_perm(remap)
        Xc16, base16 = Xc16[:, perm, :], base16[perm, :]

    if mode == "all":
        Xc, base = Xc16, base16
    elif mode == "refl":
        rows = [_full16_row(p, p) for p in ports]    # reflection channels Sii only
        Xc, base = Xc16[:, rows, :], base16[rows, :]
    elif mode == "pair":
        a, b = ports
        # map the 2 antennas to the 4-channel [S11, S12, S22, S21] convention:
        #   S11 <- S_aa,  S12 <- S_ab,  S22 <- S_bb,  S21 <- S_ba
        rows = [_full16_row(a, a), _full16_row(a, b),
                _full16_row(b, b), _full16_row(b, a)]
        Xc, base = Xc16[:, rows, :], base16[rows, :]
    else:  # single
        a = ports[0]
        rows = [_full16_row(a, a)]               # S_aa only
        Xc, base = Xc16[:, rows, :], base16[rows, :]

    per_pos, pos_xy = {}, {}
    for p in np.unique(ypos):
        m = ypos == p
        per_pos[int(p)] = Xc[m]
        pos_xy[int(p)] = (float(xy[m][0, 0]), float(xy[m][0, 1]))
    return per_pos, base, pos_xy


def calibrate(Xc, base_c, mean_sub=True):
    Y = Xc - base_c[None, :, :]
    if mean_sub:
        Y = Y - Y.mean(axis=0, keepdims=True)  # per-session mean subtraction
    return Y


def _build_raw(Y):
    """Raw S-parameters only: magnitude + phase per channel per freq (the same
    two quantities the CNN's raw image uses), flattened. (N, 2*F*C)."""
    mag = np.abs(Y).astype(np.float32)
    ph = np.angle(Y).astype(np.float32)
    N, C, F = Y.shape
    return np.concatenate([mag.reshape(N, C * F), ph.reshape(N, C * F)], axis=1)


def _build_tdr(Y, n_bins=N_TDR_BINS):
    """IFFT / TDR envelope ONLY: |ifft(Y)| first n_bins per channel. (N, n_bins*C)."""
    env = np.abs(np.fft.ifft(Y, axis=-1)[:, :, :n_bins]).astype(np.float32)
    return env.reshape(Y.shape[0], -1)


def _build_physics(Y, n_bins=N_TDR_BINS):
    """MATCHED physics: per channel [mag, phase, real, imag] (freq-domain) plus
    the |ifft| TDR envelope. NO per-trace stats / reciprocity / ratios, so it is
    exactly the feature set the CNN's physics image also gets. (N, C*(4F + n_bins))."""
    N, C, F = Y.shape
    mag = np.abs(Y).astype(np.float32)
    ph = np.angle(Y).astype(np.float32)
    re = np.real(Y).astype(np.float32)
    im = np.imag(Y).astype(np.float32)
    env = np.abs(np.fft.ifft(Y, axis=-1)[:, :, :n_bins]).astype(np.float32)
    return np.concatenate([mag.reshape(N, C * F), ph.reshape(N, C * F),
                           re.reshape(N, C * F), im.reshape(N, C * F),
                           env.reshape(N, C * n_bins)], axis=1)


def build_features(Y, mode, input_kind):
    """Y: (N, C, F) calibrated complex.  input_kind in {raw, physics, tdr}.
    These are defined IDENTICALLY to the CNN's inputs for a matched comparison."""
    if input_kind == "raw":
        return _build_raw(Y)
    if input_kind == "tdr":
        return _build_tdr(Y)
    return _build_physics(Y)


def _fit_predict(seed, X_tr, y_tr, X_te):
    clf = MLPClassifier(hidden_layer_sizes=(256, 128), max_iter=200,
                        early_stopping=True, validation_fraction=0.1,
                        n_iter_no_change=15, random_state=seed, verbose=False)
    clf.fit(X_tr, y_tr)
    return clf.predict_proba(X_te)


def train_predict(X_tr, y_tr, X_te, use_logreg=True):
    mu = X_tr.mean(0); sd = X_tr.std(0) + 1e-8
    X_tr_z = (X_tr - mu) / sd; X_te_z = (X_te - mu) / sd
    sc = StandardScaler().fit(X_tr_z)
    X_tr_s = sc.transform(X_tr_z); X_te_s = sc.transform(X_te_z)
    probs_list = Parallel(n_jobs=len(ENSEMBLE_SEEDS), backend="threading")(
        delayed(_fit_predict)(es, X_tr_s, y_tr, X_te_s) for es in ENSEMBLE_SEEDS)
    probs = np.mean(probs_list, axis=0)
    if use_logreg:
        lr = LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs", random_state=42)
        lr.fit(X_tr_s, y_tr)
        probs = (probs * len(ENSEMBLE_SEEDS) + lr.predict_proba(X_te_s)) / (len(ENSEMBLE_SEEDS) + 1)
    return probs.argmax(1)


def pos_rc(pos_id):
    """sparse pos id -> (row, col) 1-indexed.  pos = ((r-1)*COLS+(c-1))*4+(p-1)."""
    cell = pos_id // 4
    return cell // TOTAL_COLS + 1, cell % TOTAL_COLS + 1


def quadrant_of(pos_id, row_mid, col_mid):
    r, c = pos_rc(pos_id)
    if r <= row_mid and c <= col_mid: return 0   # top-left
    if r <= row_mid and c >  col_mid: return 1   # top-right
    if r >  row_mid and c <= col_mid: return 2   # bottom-left
    return 3                                     # bottom-right


def hierarchical_predict(X_tr, y_tr, X_te, quad_of_dense):
    """Two-stage: Stage 1 predicts quadrant, Stage 2 predicts the exact position
    within the predicted quadrant. Same train_predict (ensemble+LogReg) at each
    stage. Returns global dense position labels for each test sample."""
    quad_tr = np.array([quad_of_dense[y] for y in y_tr])
    quads = sorted(set(quad_tr.tolist()))
    qd = {q: i for i, q in enumerate(quads)}
    yq_tr = np.array([qd[q] for q in quad_tr])
    pred_qd = train_predict(X_tr, yq_tr, X_te, use_logreg=True)
    pred_q = np.array([quads[d] for d in pred_qd])

    pred_pos = np.full(len(X_te), -1, dtype=np.int64)
    for q in quads:
        tr_m = quad_tr == q
        te_m = pred_q == q
        if not te_m.any():
            continue
        pos_in_q = sorted(set(y_tr[tr_m].tolist()))
        if len(pos_in_q) == 1:
            pred_pos[te_m] = pos_in_q[0]; continue
        loc = {p: i for i, p in enumerate(pos_in_q)}
        ylocal = np.array([loc[p] for p in y_tr[tr_m]])
        pl = train_predict(X_tr[tr_m], ylocal, X_te[te_m], use_logreg=True)
        pred_pos[te_m] = np.array([pos_in_q[d] for d in pl])
    return pred_pos


def per_pos_vote(ypos_te, pred, label_to_pos):
    by_pos = defaultdict(list)
    for tp, pp in zip(ypos_te, pred):
        by_pos[int(tp)].append(int(pp))
    correct, per_pos = 0, {}
    for tp, preds in by_pos.items():
        u, c = np.unique(preds, return_counts=True)
        winner = label_to_pos[int(u[c.argmax()])]
        ok = (winner == int(tp))
        per_pos[int(tp)] = 1.0 if ok else 0.0
        correct += int(ok)
    return correct / max(1, len(by_pos)), per_pos


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", required=True,
                    help="parent folder holding the per-session subfolders")
    ap.add_argument("--antenna", default="all",
                    help="all | pair:1,3 | pair:2,4 | single:1 ...")
    ap.add_argument("--input", dest="input_kind", default="physics",
                    choices=["raw", "physics", "tdr"],
                    help="input representation: raw (mag+phase) | physics (full "
                         "derived) | tdr (IFFT/TDR envelope only)")
    ap.add_argument("--sessions", default="",
                    help="comma list of session name substrings to KEEP, "
                         "e.g. 1432,1454,1516 (default: all sessions)")
    ap.add_argument("--set-label", dest="set_label", default="",
                    help="label for this session set (default: <N>sess)")
    ap.add_argument("--port-remap", dest="port_remap", default="",
                    help="relabel antenna ports before subsetting, e.g. 2,1,4,3 "
                         "(new port a <- old port list[a-1]). Use for June18 empty.")
    ap.add_argument("--hier", action="store_true",
                    help="two-stage hierarchical: predict quadrant then position.")
    ap.add_argument("--no-zscore", dest="no_zscore", action="store_true",
                    help="ablation: skip the per-session z-score entirely")
    ap.add_argument("--no-session-mean", dest="no_session_mean", action="store_true",
                    help="ABLATION: skip the per-session mean subtraction "
                         "(keep only baseline subtraction).")
    args = ap.parse_args()
    remap = [int(x) for x in args.port_remap.replace(" ", "").split(",")] if args.port_remap else None

    mode, ports = parse_antenna(args.antenna)
    parent = Path(args.setup)
    setup_name = parent.name
    only = [t for t in args.sessions.replace(" ", "").split(",") if t] or None

    sess_files = list_sessions(parent, only=only)
    set_label = args.set_label.strip() or f"{len(sess_files)}sess"
    if args.no_zscore:
        set_label += "-zsoff"           # keep ablation outputs separate
    if args.no_session_mean:
        set_label += "-nomean"          # keep ablation outputs separate
    if len(sess_files) < 2:
        print(f"[ERROR] LOSO needs >=2 sessions; found {len(sess_files)} in {parent}")
        return
    print("=" * 66)
    print(f"MLP LOSO  --  {setup_name}  [{set_label}]  --  {mode.upper()} ports {ports}")
    print(f"  sessions: {[n for n, _ in sess_files]}")
    print("=" * 66)

    sessions = {}
    for name, path in sess_files:
        t0 = time.time()
        per_pos, base_c, pos_xy = load_session(path, mode, ports, remap=remap)
        sessions[name] = (per_pos, base_c, pos_xy)
        print(f"  loaded {name}: {len(per_pos)} positions  ({time.time()-t0:.1f}s)")

    # valid positions = present in every session
    pos_sets = [set(pp.keys()) for pp, _, _ in sessions.values()]
    valid = sorted(set.intersection(*pos_sets))
    n_classes = len(valid)
    pos_to_label = {p: i for i, p in enumerate(valid)}
    label_to_pos = valid
    print(f"  common positions: {n_classes}  (chance {100/n_classes:.2f}%)")

    # quadrant split (for hierarchical): midpoint of measured rows/cols
    rs = sorted(set(pos_rc(p)[0] for p in valid))
    cs = sorted(set(pos_rc(p)[1] for p in valid))
    row_mid, col_mid = rs[len(rs)//2 - 1], cs[len(cs)//2 - 1]
    quad_of_dense = [quadrant_of(valid[d], row_mid, col_mid) for d in range(n_classes)]
    if args.hier:
        import collections as _c
        qc = _c.Counter(quad_of_dense)
        print(f"  HIERARCHICAL: quadrants (rowMid={row_mid},colMid={col_mid}) "
              f"positions per quad = {dict(sorted(qc.items()))}")

    # precompute features per session
    feats, yposes = {}, {}
    for name, (per_pos, base_c, _) in sessions.items():
        Xc = np.concatenate([per_pos[p] for p in valid], axis=0)
        ypos = np.concatenate([np.full(per_pos[p].shape[0], p) for p in valid]).astype(np.int64)
        Y = calibrate(Xc, base_c, mean_sub=not args.no_session_mean)
        feats[name] = build_features(Y, mode, args.input_kind)
        yposes[name] = ypos

    sids = list(sessions.keys())
    fold_trial, fold_pos = [], []
    pos_correct = defaultdict(int); pos_total = defaultdict(int)
    for test_sid in sids:
        t0 = time.time()
        train_sids = [s for s in sids if s != test_sid]
        X_tr = np.concatenate([feats[s] for s in train_sids])
        y_tr = np.concatenate([np.array([pos_to_label[int(p)] for p in yposes[s]])
                               for s in train_sids])
        sess_tr = np.concatenate([np.full(feats[s].shape[0], j)
                                  for j, s in enumerate(train_sids)])
        X_te = feats[test_sid]
        y_te = np.array([pos_to_label[int(p)] for p in yposes[test_sid]])
        ypos_te = yposes[test_sid]

        if args.no_zscore:
            X_tr_z, X_te_z = X_tr, X_te                        # ablation: raw
        else:
            X_tr_z, _ = per_session_zscore(X_tr, sess_tr)      # the KEY trick
            mu = X_te.mean(0); sd = X_te.std(0) + 1e-8
            X_te_z = (X_te - mu) / sd

        if args.hier:
            pred = hierarchical_predict(X_tr_z, y_tr, X_te_z, quad_of_dense)
        else:
            pred = train_predict(X_tr_z, y_tr, X_te_z, use_logreg=True)
        trial = float((pred == y_te).mean()) * 100
        pos, per_pos_ok = per_pos_vote(ypos_te, pred, label_to_pos)
        fold_trial.append(trial); fold_pos.append(pos * 100)
        for p, ok in per_pos_ok.items():
            pos_correct[p] += int(ok); pos_total[p] += 1
        print(f"  fold test={test_sid}:  trial={trial:5.2f}%   position-vote={pos*100:5.2f}%   ({time.time()-t0:.1f}s)")

    per_position = []
    for p in valid:
        xy = sessions[sids[0]][2].get(p, (float('nan'), float('nan')))
        acc = 100 * pos_correct[p] / pos_total[p] if pos_total[p] else 0.0
        per_position.append(dict(pos=int(p), x=xy[0], y=xy[1], acc=acc))

    result = dict(
        method="MLP", setup=setup_name, sessionSet=set_label,
        inputKind=args.input_kind, freqGrid="native791",
        classifier=("hierarchical" if args.hier else "single"),
        antennaMode=mode, ports=list(ports),
        numSessions=len(sids), sessionNames=sids, numClasses=n_classes,
        chancePct=100/n_classes,
        foldTrialAcc=fold_trial, foldPosAcc=fold_pos,
        losoTrialMean=float(np.mean(fold_trial)), losoTrialStd=float(np.std(fold_trial)),
        losoPosMean=float(np.mean(fold_pos)),   losoPosStd=float(np.std(fold_pos)),
        perPosition=per_position,
    )
    ports_tag = "-".join(str(p) for p in ports)
    clf_tag = "hier_" if args.hier else ""
    tag = f"{setup_name}_{set_label}_{clf_tag}{args.input_kind}_{mode}_ant{ports_tag}".replace(" ", "_")
    out = RESULTS_DIR / f"mlp_loso_{tag}.json"
    with open(out, "w") as f:
        json.dump(result, f, indent=2)

    print("-" * 66)
    print(f"  LOSO trial-level   : {result['losoTrialMean']:.2f} +/- {result['losoTrialStd']:.2f} %")
    print(f"  LOSO position-vote : {result['losoPosMean']:.2f} +/- {result['losoPosStd']:.2f} %")
    print(f"  chance             : {100/n_classes:.2f} %  ({n_classes}-way)")
    print(f"  saved {out}")


if __name__ == "__main__":
    main()
