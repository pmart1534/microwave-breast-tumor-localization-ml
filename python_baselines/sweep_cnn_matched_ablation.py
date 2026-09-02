r"""CNN-matched preprocessing ablation for classical methods.

The classical pipeline now applies the SAME 5 steps as the CNN by default:
    step 1: complexify/channel/band (--input physics: mag/phase channels)
    step 2: baseline subtraction        (--no-baseline    disables)
    step 3: per-session mean subtract   (--no-session-mean disables)
    step 4: per-session z-score         (--no-zscore      disables)
    step 5: frozen input-layer z-score  (--no-input-norm  disables)

This grid produces the three tables Peter uses for CNN:
    Full        : (no flags)
    Remove one  : 4 variants, each drops one of steps 2-5
    Keep one    : 4 variants, each keeps only one of steps 2-5
    All off     : all 4 flags on

Conditions: reference (baseline3_Aug18) and antenna swap (swapAnt4).
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

# variant_label -> flags disabling steps NOT in this variant
VARIANTS = [
    ("full",              []),
    # Remove-one:
    ("rm-baseline",       ["--no-baseline"]),
    ("rm-sessmean",       ["--no-session-mean"]),
    ("rm-persesszs",      ["--no-zscore"]),
    ("rm-inputnorm",      ["--no-input-norm"]),
    # Keep-one:
    ("only-baseline",     ["--no-session-mean", "--no-zscore", "--no-input-norm"]),
    ("only-sessmean",     ["--no-baseline",    "--no-zscore", "--no-input-norm"]),
    ("only-persesszs",    ["--no-baseline",    "--no-session-mean", "--no-input-norm"]),
    ("only-inputnorm",    ["--no-baseline",    "--no-session-mean", "--no-zscore"]),
    # All off:
    ("all-off",           ["--no-baseline", "--no-session-mean", "--no-zscore", "--no-input-norm"]),
]

CLFS = "rf,lr,knn"
grid = list(itertools.product(CONDITIONS, VARIANTS))
print(f"total cells: {len(grid)}")
t_all = time.time()

for i, ((cond_label, setup, sess_filter, set_label),
        (var_label, flags)) in enumerate(grid, 1):
    cmd = [PY, str(HERE / "run_baselines_loso.py"),
           "--setup",   setup,
           "--antenna", "all",
           "--input",   "physics",
           "--set-label", f"{set_label}_{var_label}",
           "--classifiers", CLFS] + flags
    if sess_filter:
        cmd += ["--sessions", sess_filter]
    print(f"\n[{i:2d}/{len(grid)}] cond={cond_label:8s} variant={var_label}", flush=True)
    t0 = time.time()
    subprocess.run(cmd)
    print(f"  done in {time.time()-t0:.1f}s", flush=True)

print(f"\nALL DONE in {(time.time()-t_all)/60:.1f} min")
