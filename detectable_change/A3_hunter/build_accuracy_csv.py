r"""
build_accuracy_csv.py
=====================
Emit per-position accuracy CSVs (the "dot size" input for paper_figure_A3.py)
from the CNN-vs-MLP LOSO result JSONs in ..\..\..\..\CNN vs MLP\results\.

MATCHED-PIPELINE EDITION: selects runs by JSON *content*, not filename glob —
only runs from the matched pipeline (native 791-pt grid, identical calibration
+ per-session z-score in both models) qualify:
    inputKind  == INPUT_KIND (default "raw")
    classifier == "single"
    sessionSet == required set (F5 = last3)
    antennaMode/ports == the requested antenna mode

Writes accuracy_data/per_position_accuracy_<config>_<antmode>__<method>.csv
with columns  label,x_in,y_in,accuracy,n_correct,n_total   (accuracy 0..1).
"""
from __future__ import annotations
import json, glob, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACC_DIR = HERE / "accuracy_data"
ACC_DIR.mkdir(exist_ok=True)
CNNMLP_RESULTS = Path(r"C:\Users\peter\Desktop\EM Imaging\CNN vs MLP\results")

TOTAL_COLS = 6
INPUT_KIND = "raw"          # which matched input drives dot size: raw|physics|tdr

# antmode -> (antennaMode, ports)
ANTMODES = {
    "single1":     ("single", [1]),
    "pair13":      ("pair",   [1, 3]),
    "all":         ("all",    [1, 2, 3, 4]),
    "refl_pair13": ("refl",   [1, 3]),
    "refl_all":    ("refl",   [1, 2, 3, 4]),
}

# A3 config -> (setup name in JSON, required sessionSet)
# Env A3_SSET_SUFFIX (e.g. "-nomean") selects the pipeline-v2 runs instead.
_SS = os.environ.get("A3_SSET_SUFFIX", "")
CONFIGS = {
    "A3_Empty": ("June18",       "remap" + _SS),
    "A3_F4":    ("A3_F4_SamMed", "all4" + _SS),
    "A3_F5":    ("A3_F5_SamMed", "last3" + _SS),   # latter-3 sessions only
}


def pos_to_label(pos):
    p = pos % 4 + 1
    rc = pos // 4
    return f"R{rc // TOTAL_COLS + 1}C{rc % TOTAL_COLS + 1}P{p}"


def norm_ports(p):
    if not isinstance(p, (list, tuple)):
        p = [p]
    return sorted(int(x) for x in p)


def find_run(method, setup, sset, mode, ports):
    for f in sorted(glob.glob(str(CNNMLP_RESULTS / f"{method}_loso_*.json"))):
        try:
            r = json.loads(Path(f).read_text())
        except Exception:
            continue
        if r.get("setup") != setup:               continue
        if r.get("sessionSet") != sset:           continue
        if r.get("inputKind") != INPUT_KIND:      continue
        if r.get("classifier", "single") != "single":  continue
        if r.get("antennaMode") != mode:          continue
        if norm_ports(r.get("ports", [])) != ports:    continue
        return r, os.path.basename(f)
    return None, None


def main():
    print(f"[input kind: {INPUT_KIND} | matched pipeline only]")
    for config, (setup, sset) in CONFIGS.items():
        for antmode, (mode, ports) in ANTMODES.items():
            for method in ("cnn", "mlp"):
                r, fname = find_run(method, setup, sset, mode, ports)
                if r is None:
                    print(f"[!] no matched {method} run: {config}/{antmode} "
                          f"({INPUT_KIND}, {sset}) -- skipped")
                    continue
                folds = r.get("numSessions", 0)
                rows = []
                for e in r.get("perPosition", []):
                    acc = float(e.get("acc", 0.0)) / 100.0
                    label = e["label"] if "label" in e else pos_to_label(int(e["pos"]))
                    rows.append((label, e.get("x"), e.get("y"), acc,
                                 int(round(acc * folds)) if folds else "", folds))
                out = ACC_DIR / f"per_position_accuracy_{config}_{antmode}__{method}.csv"
                with open(out, "w") as f:
                    f.write("label,x_in,y_in,accuracy,n_correct,n_total\n")
                    for L, x, y, acc, nc, nt in sorted(rows):
                        xs = f"{x:.4f}" if isinstance(x, (int, float)) else ""
                        ys = f"{y:.4f}" if isinstance(y, (int, float)) else ""
                        f.write(f"{L},{xs},{ys},{acc:.4f},{nc},{nt}\n")
                print(f"  {out.name}  ({len(rows)} pos, from {fname})")


if __name__ == "__main__":
    main()
