"""
parse_accuracy_txt.py
=====================
Parses the SpatialAcc_WithinSession_*.txt files produced by the MATLAB
spatial-accuracy script and writes one CSV per configuration that
`brainstorm_variations.py` (and any other downstream tool) can read.

Input files:
  BreastPhantom/WithoutGlandular/DATA/SpatialAcc_..._NoGlandular_*.txt    -> A2_Empty
  BreastPhantom/WithGlandular/DATA/SpatialAcc_...F4...*.txt               -> A2_F4
  BreastPhantom/WithGlandular/DATA/SpatialAcc_...F5...*.txt               -> A2_F5

Output (this folder):
  accuracy_data/per_position_accuracy_A2_Empty.csv
  accuracy_data/per_position_accuracy_A2_F4.csv
  accuracy_data/per_position_accuracy_A2_F5.csv
  accuracy_data/overall_accuracy_summary.json

CSV columns: label, x_in, y_in, accuracy, n_correct, n_total
  accuracy in 0.0 - 1.0 (NaN if no test samples at that position).
"""
from __future__ import annotations
import os, re, json, glob

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "accuracy_data")
os.makedirs(OUT, exist_ok=True)

# By default this script searches for SpatialAcc_*.txt files next to each
# .mat dataset under <repo>/datasets/<config>/. If your MATLAB output lives
# somewhere else, set the SPATIALACC_DIR environment variable to that folder
# and re-run.
DATASETS_DIR = os.path.abspath(os.path.join(HERE, os.pardir, "datasets"))
ENV_DIR = os.environ.get("SPATIALACC_DIR")

# (config_name, search_dir, glob_pattern)
SOURCES = [
    ("A2_Empty",
     ENV_DIR or os.path.join(DATASETS_DIR, "A2_Empty"),
     "SpatialAcc_WithinSession_*NoGlandular*.txt"),
    ("A2_F4",
     ENV_DIR or os.path.join(DATASETS_DIR, "A2_F4"),
     "SpatialAcc_WithinSession_*F4*.txt"),
    ("A2_F5",
     ENV_DIR or os.path.join(DATASETS_DIR, "A2_F5"),
     "SpatialAcc_WithinSession_*F5*.txt"),
]

def parse_txt(path):
    overall = None
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                m = re.search(r"Overall accuracy:\s*([\d.]+)\s*%", line)
                if m:
                    overall = float(m.group(1)) / 100.0
                continue
            # Data row: "R2C2P3 , 2, 2, 3,  1.8750,  1.8750, 100.00,    10, 10"
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 9:
                continue
            label = parts[0]
            try:
                x_in = float(parts[4])
                y_in = float(parts[5])
            except ValueError:
                continue
            acc_str = parts[6]
            if acc_str.upper() == "NA":
                acc = float("nan")
            else:
                try:
                    acc = float(acc_str) / 100.0
                except ValueError:
                    acc = float("nan")
            try:
                n_correct = int(parts[7])
                n_total = int(parts[8])
            except ValueError:
                n_correct = n_total = 0
            rows.append((label, x_in, y_in, acc, n_correct, n_total))
    return overall, rows

def main():
    summary = {}
    for name, folder, pattern in SOURCES:
        matches = sorted(glob.glob(os.path.join(folder, pattern)))
        if not matches:
            print(f"[!] no file for {name} in {folder} matching {pattern}")
            continue
        # Use the most recently generated file if multiple
        path = max(matches, key=os.path.getmtime)
        print(f"{name:10s} <- {os.path.basename(path)}")
        overall, rows = parse_txt(path)
        out_csv = os.path.join(OUT, f"per_position_accuracy_{name}.csv")
        with open(out_csv, "w", encoding="utf-8") as f:
            f.write("label,x_in,y_in,accuracy,n_correct,n_total\n")
            for L, x, y, a, nc, nt in rows:
                a_str = "" if (a != a) else f"{a:.4f}"  # NaN -> blank
                f.write(f"{L},{x:.4f},{y:.4f},{a_str},{nc},{nt}\n")
        n_eval = sum(1 for r in rows if r[3] == r[3])  # non-NaN
        summary[name] = {
            "source": os.path.basename(path),
            "overall_accuracy": overall,
            "n_positions_with_test_samples": n_eval,
            "n_positions_total": len(rows),
        }
        print(f"  wrote {out_csv}  ({n_eval}/{len(rows)} positions evaluated, "
              f"overall {overall*100:.2f}%)")
    with open(os.path.join(OUT, "overall_accuracy_summary.json"),
              "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("\nWrote summary to", os.path.join(OUT, "overall_accuracy_summary.json"))

if __name__ == "__main__":
    main()
