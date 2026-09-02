r"""Classical-baselines LOSO driver — SVM, Random Forest, Logistic Regression,
k-NN — for direct head-to-head comparison against the CNN and MLP.

Piggybacks on run_mlp_loso.py's loading + feature pipeline exactly:
    per-session baseline calibration
    -> physics features
    -> per-session z-score
    -> classifier of choice
    -> per-position majority vote

Runs each classifier across the same LOSO folds and emits one JSON per method
with the same layout run_mlp_loso.py writes, so the results plot directly
alongside the MLP and CNN results.

Usage (from mlp_python/, with the Above 95 Percent venv):
    python run_baselines_loso.py --setup "C:\...\Aug18\A3_SamMed_MetalTumor" ^
        --sessions Session0101,Session0102,Session0103 ^
        --set-label baseline3 ^
        --classifiers svm,rf,lr,knn ^
        --antenna all

Outputs:
    ../results/<clf>_loso_<tag>.json
"""
from __future__ import annotations
import os, sys, json, argparse, time
from collections import defaultdict
from pathlib import Path
import numpy as np

# Reuse everything from run_mlp_loso.py so we can't drift out of sync.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_mlp_loso as mlp  # noqa: E402

from data import per_session_zscore                             # noqa: E402
from sklearn.svm import SVC                                     # noqa: E402
from sklearn.ensemble import RandomForestClassifier             # noqa: E402
from sklearn.linear_model import LogisticRegression             # noqa: E402
from sklearn.neighbors import KNeighborsClassifier              # noqa: E402
from sklearn.preprocessing import StandardScaler                # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
def make_clf(kind, n_classes, seed=42):
    """Return a fresh sklearn classifier for one LOSO fold.

    Sensible defaults chosen once; no per-fold hyperparameter tuning to
    avoid nested-CV blowup on 3 sessions. The paper's story is a like-for-
    like comparison, not a hyperparameter-search win.
    """
    if kind == "svm":
        # Linear SVM: fast, well-calibrated on high-D physics features, and
        # gives the fairest "linear-classifier baseline" reference.
        return SVC(kernel="linear", C=1.0, decision_function_shape="ovr")
    if kind == "svm_rbf":
        return SVC(kernel="rbf", C=1.0, gamma="scale")
    if kind == "rf":
        return RandomForestClassifier(
            n_estimators=400, max_features="sqrt", n_jobs=-1, random_state=seed)
    if kind == "lr":
        return LogisticRegression(
            C=1.0, penalty="l2", solver="lbfgs",
            max_iter=2000, n_jobs=-1)
    if kind == "knn":
        return KNeighborsClassifier(n_neighbors=5, weights="distance", n_jobs=-1)
    if kind == "mlp":
        # Matches the 256-128 topology promised in the paper's Methods II-H.
        from sklearn.neural_network import MLPClassifier
        return MLPClassifier(hidden_layer_sizes=(256, 128), max_iter=400,
                             early_stopping=False, random_state=seed)
    raise ValueError(f"unknown classifier: {kind}")


def train_predict(kind, X_tr, y_tr, X_te):
    clf = make_clf(kind, n_classes=int(y_tr.max()) + 1)
    clf.fit(X_tr, y_tr)
    return clf.predict(X_te)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", required=True,
                    help="parent folder holding per-session subfolders")
    ap.add_argument("--antenna", default="all",
                    help="all | pair:1,3 | pair:2,4 | single:1 ...")
    ap.add_argument("--input", dest="input_kind", default="physics",
                    choices=["raw", "physics", "tdr"])
    ap.add_argument("--sessions", default="",
                    help="comma list of session-name substrings to KEEP")
    ap.add_argument("--set-label", dest="set_label", default="",
                    help="label for this session set (default: <N>sess)")
    ap.add_argument("--port-remap", dest="port_remap", default="")
    ap.add_argument("--classifiers", default="svm,rf,lr,knn",
                    help="comma list: svm, svm_rbf, rf, lr, knn")
    ap.add_argument("--band", default="",
                    help='freq band in GHz "lo-hi" (e.g. "1-2", "2-4"); '
                         'default = full 0.1-8 GHz native grid')
    ap.add_argument("--no-zscore", dest="no_zscore", action="store_true")
    ap.add_argument("--no-session-mean", dest="no_session_mean",
                    action="store_true")
    ap.add_argument("--no-baseline", dest="no_baseline", action="store_true",
                    help="ablation: skip complex-domain baseline subtraction "
                         "(the no-tumor sweep -> tumor sweep step)")
    ap.add_argument("--no-input-norm", dest="no_input_norm", action="store_true",
                    help="ablation: skip the frozen input-layer z-score (CNN step 5). "
                         "Default pipeline applies both per-session z-score and frozen "
                         "train-set z-score, matching the CNN's five-step pipeline.")
    args = ap.parse_args()

    remap = ([int(x) for x in args.port_remap.replace(" ", "").split(",")]
             if args.port_remap else None)
    mode, ports = mlp.parse_antenna(args.antenna)
    parent = Path(args.setup)
    setup_name = parent.name
    only = [t for t in args.sessions.replace(" ", "").split(",") if t] or None
    clfs = [c.strip().lower() for c in args.classifiers.split(",") if c.strip()]

    sess_files = mlp.list_sessions(parent, only=only)
    # Parse frequency band (default = full native 0.1-8 GHz, 791 pts)
    band_mask = None; band_tag = "full"
    if args.band:
        lo_ghz, hi_ghz = [float(x) for x in args.band.split("-")]
        band_mask = (mlp.NATIVE_FREQ >= lo_ghz * 1e9) & (mlp.NATIVE_FREQ <= hi_ghz * 1e9)
        band_tag = f"{lo_ghz:g}-{hi_ghz:g}GHz"

    set_label = args.set_label.strip() or f"{len(sess_files)}sess"
    if args.band:            set_label += f"-band{band_tag}"
    if args.no_zscore:       set_label += "-zsoff"
    if args.no_session_mean: set_label += "-nomean"
    if args.no_baseline:     set_label += "-nobase"
    if args.no_input_norm:   set_label += "-innoff"
    if len(sess_files) < 2:
        print(f"[ERROR] LOSO needs >=2 sessions; found {len(sess_files)}")
        return

    print("=" * 72)
    print(f"BASELINES LOSO  --  {setup_name}  [{set_label}]  --  "
          f"{mode.upper()} ports {ports}")
    print(f"  sessions   : {[n for n, _ in sess_files]}")
    print(f"  classifiers: {clfs}")
    print("=" * 72)

    sessions = {}
    for name, path in sess_files:
        t0 = time.time()
        per_pos, base_c, pos_xy = mlp.load_session(path, mode, ports, remap=remap)
        sessions[name] = (per_pos, base_c, pos_xy)
        print(f"  loaded {name}: {len(per_pos)} positions  ({time.time()-t0:.1f}s)")

    pos_sets = [set(pp.keys()) for pp, _, _ in sessions.values()]
    valid = sorted(set.intersection(*pos_sets))
    n_classes = len(valid)
    pos_to_label = {p: i for i, p in enumerate(valid)}
    label_to_pos = valid
    print(f"  common positions: {n_classes}  (chance {100/n_classes:.2f}%)")

    feats, yposes = {}, {}
    for name, (per_pos, base_c, _) in sessions.items():
        Xc = np.concatenate([per_pos[p] for p in valid], axis=0)
        ypos = np.concatenate(
            [np.full(per_pos[p].shape[0], p) for p in valid]).astype(np.int64)
        # Full preprocessing pipeline (default):
        #   Y = (raw - no-tumor baseline) - per-session mean
        # --no-baseline skips the first subtraction; --no-session-mean the second.
        if args.no_baseline:
            Y = Xc.copy()  # raw complex S-parameters, no baseline sub
            if not args.no_session_mean:
                Y = Y - Y.mean(axis=0, keepdims=True)
        else:
            Y = mlp.calibrate(Xc, base_c, mean_sub=not args.no_session_mean)
        if band_mask is not None:
            Y = Y[:, :, band_mask]
        feats[name] = mlp.build_features(Y, mode, args.input_kind)
        yposes[name] = ypos

    sids = list(sessions.keys())

    # Prep LOSO folds once and reuse across classifiers.
    fold_data = []
    for test_sid in sids:
        train_sids = [s for s in sids if s != test_sid]
        X_tr = np.concatenate([feats[s] for s in train_sids])
        y_tr = np.concatenate([np.array([pos_to_label[int(p)] for p in yposes[s]])
                               for s in train_sids])
        sess_tr = np.concatenate([np.full(feats[s].shape[0], j)
                                  for j, s in enumerate(train_sids)])
        X_te = feats[test_sid]
        y_te = np.array([pos_to_label[int(p)] for p in yposes[test_sid]])
        ypos_te = yposes[test_sid]

        # CNN-matching pipeline: step 4 = per-session z-score (each session
        # uses its own stats, including the test session); step 5 = frozen
        # input-layer z-score using pooled training stats.  Both on by
        # default; --no-zscore disables step 4; --no-input-norm disables step 5.
        if args.no_zscore:
            X_tr_z, X_te_z = X_tr, X_te
        else:
            X_tr_z, _ = per_session_zscore(X_tr, sess_tr)
            mu = X_te.mean(0); sd = X_te.std(0) + 1e-8
            X_te_z = (X_te - mu) / sd
        if not args.no_input_norm:
            mu = X_tr_z.mean(0); sd = X_tr_z.std(0) + 1e-8
            X_tr_z = (X_tr_z - mu) / sd
            X_te_z = (X_te_z - mu) / sd
        fold_data.append(dict(test=test_sid, X_tr=X_tr_z, y_tr=y_tr,
                              X_te=X_te_z, y_te=y_te, ypos_te=ypos_te))

    # Run each classifier over all folds, save one JSON per classifier.
    for kind in clfs:
        print("-" * 72)
        print(f"  === {kind.upper()} ===")
        fold_trial, fold_pos = [], []
        pos_correct = defaultdict(int); pos_total = defaultdict(int)
        for fd in fold_data:
            t0 = time.time()
            pred = train_predict(kind, fd["X_tr"], fd["y_tr"], fd["X_te"])
            trial = float((pred == fd["y_te"]).mean()) * 100
            pos, per_pos_ok = mlp.per_pos_vote(fd["ypos_te"], pred, label_to_pos)
            fold_trial.append(trial); fold_pos.append(pos * 100)
            for p, ok in per_pos_ok.items():
                pos_correct[p] += int(ok); pos_total[p] += 1
            print(f"    fold test={fd['test']:>40s}  "
                  f"trial={trial:5.2f}%  pos-vote={pos*100:5.2f}%  "
                  f"({time.time()-t0:.1f}s)")

        per_position = []
        for p in valid:
            xy = sessions[sids[0]][2].get(p, (float('nan'), float('nan')))
            acc = 100 * pos_correct[p] / pos_total[p] if pos_total[p] else 0.0
            per_position.append(dict(pos=int(p), x=xy[0], y=xy[1], acc=acc))

        result = dict(
            method=kind.upper(),
            setup=setup_name, sessionSet=set_label,
            inputKind=args.input_kind, freqGrid="native791",
            classifier="single",
            antennaMode=mode, ports=list(ports),
            numSessions=len(sids), sessionNames=sids,
            numClasses=n_classes, chancePct=100/n_classes,
            foldTrialAcc=fold_trial, foldPosAcc=fold_pos,
            losoTrialMean=float(np.mean(fold_trial)),
            losoTrialStd=float(np.std(fold_trial)),
            losoPosMean=float(np.mean(fold_pos)),
            losoPosStd=float(np.std(fold_pos)),
            perPosition=per_position,
        )
        ports_tag = "-".join(str(p) for p in ports)
        tag = (f"{setup_name}_{set_label}_{args.input_kind}_{mode}"
               f"_ant{ports_tag}").replace(" ", "_")
        out = RESULTS_DIR / f"{kind}_loso_{tag}.json"
        with open(out, "w") as f:
            json.dump(result, f, indent=2)
        print(f"    LOSO trial-level   : "
              f"{result['losoTrialMean']:.2f} +/- {result['losoTrialStd']:.2f} %")
        print(f"    LOSO position-vote : "
              f"{result['losoPosMean']:.2f} +/- {result['losoPosStd']:.2f} %")
        print(f"    chance             : {100/n_classes:.2f} %  "
              f"({n_classes}-way)")
        print(f"    saved {out}")


if __name__ == "__main__":
    main()
