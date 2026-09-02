r"""SVM + MLP antenna-subset sweep with the CNN-matched full pipeline.

Fills the two classifiers promised in Methods II-H but missing from Table V:
    conditions:  reference (baseline3_Aug18) and antenna swap (swapAnt4)
    antennas:    all-4, pair-1&3, single-1
    classifiers: linear SVM, MLP (256-128)
Uses the same "_antsubset" set-label as the RF/LR/kNN runs so results align.
"""
import subprocess, itertools, time
from pathlib import Path

PY   = r"C:\Users\peter\Desktop\EM Imaging\Above 95 Percent\venv\Scripts\python.exe"
HERE = Path(__file__).resolve().parent

CONDITIONS = [
    ("pristine",
     r"C:\Users\peter\Desktop\EM Imaging\BreastPhantom\HunterVNA\DataMeasurements\Sam Antennas\MediumAntenna\Separated\Aug18",
     "1143,1210,1239",
     "baseline3_Aug18"),
    ("swap",
     r"C:\Users\peter\Desktop\EM Imaging\BreastPhantom\HunterVNA\DataMeasurements\Sam Antennas\MediumAntenna\Separated\Aug18\A3_MetalTumor_SwapAntLocation",
     "",
     "swapAnt4"),
]

ANTENNAS = ["all", "pair:1,3", "single:1"]
CLFS = "svm,mlp"

grid = list(itertools.product(CONDITIONS, ANTENNAS))
print(f"total cells: {len(grid)} (x 2 classifiers each)")
t_all = time.time()

for i, ((cond_label, setup, sess_filter, set_label), antenna) in enumerate(grid, 1):
    cmd = [PY, str(HERE / "run_baselines_loso.py"),
           "--setup",   setup,
           "--antenna", antenna,
           "--input",   "physics",
           "--set-label", f"{set_label}_antsubset",
           "--classifiers", CLFS]
    if sess_filter:
        cmd += ["--sessions", sess_filter]
    print(f"\n[{i}/{len(grid)}] cond={cond_label:8s} antenna={antenna}", flush=True)
    t0 = time.time()
    subprocess.run(cmd)
    print(f"  done in {time.time()-t0:.1f}s", flush=True)

print(f"\nALL DONE in {(time.time()-t_all)/60:.1f} min")
