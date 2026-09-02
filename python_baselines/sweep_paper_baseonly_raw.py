r"""Definitive classical Table V sweep: raw 32x791 mag/phase input (flattened),
preprocessing = baseline subtraction ONLY (session-level steps off; the frozen
train-set z-score stays, mirroring the CNN's input-layer normalization).
5 classifiers x 2 conditions x 3 antenna modes = 30 cells.
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
CLFS = "svm,rf,lr,knn,mlp"
FLAGS = ["--no-session-mean", "--no-zscore", "--no-input-norm"]  # baseline sub ONLY

grid = list(itertools.product(CONDITIONS, ANTENNAS))
print(f"total cells: {len(grid)} (x 5 classifiers each)")
t_all = time.time()
for i, ((cond, setup, sess, label), ant) in enumerate(grid, 1):
    cmd = [PY, str(HERE / "run_baselines_loso.py"),
           "--setup", setup, "--antenna", ant, "--input", "raw",
           "--set-label", f"{label}_paperBO", "--classifiers", CLFS] + FLAGS
    if sess:
        cmd += ["--sessions", sess]
    print(f"\n[{i}/{len(grid)}] cond={cond:8s} antenna={ant}", flush=True)
    t0 = time.time()
    subprocess.run(cmd)
    print(f"  done in {time.time()-t0:.1f}s", flush=True)
print(f"\nALL DONE in {(time.time()-t_all)/60:.1f} min")
