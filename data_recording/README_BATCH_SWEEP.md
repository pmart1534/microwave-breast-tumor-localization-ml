# Batch Sweep for Hunter VNA (MN7021A)

`batch_sweep` is a C program for the Hunter that does the same workflow as
your MATLAB `Imager_DataRecording.m` did for the P9371A:

- One operator session covers all grid positions x all trials
- One folder per session, named with model + object + timestamp
- Each measurement gets a labeled CSV: `R<row>C<col>P<sub>_T<trial>.csv`
- Baseline measurements get their own files: `baseline_T<trial>.csv`
- Session metadata (operator, antenna, grid config, etc.) written up front
- Interactive mode (press Enter per sweep) OR Automatic mode (configurable delay)
- Operator can skip positions on the fly

No more manually saving 640 timestamped CSVs and trying to figure out
which one belongs to which cell afterward.

---

## What's in this folder

| File | Purpose |
|---|---|
| `batch_sweep.c` | The C program. Drop it next to `sweep.c` in the application folder. |
| `README_BATCH_SWEEP.md` | This file. |

`batch_sweep.c` is a complete, self-contained source file. It is a patched
copy of Keysight's stock `sweep.c` — all of Keysight's calibration /
connection / cal-kit logic is preserved unchanged. The only new code:

1. A **batch session setup block** near the top of `main()` that collects
   model/antenna/object/operator/grid/trial-count BEFORE the normal
   Keysight setup prompts run.
2. A **position x trial loop** that replaces the original "Do you want to
   repeat the sweep?" loop near the end. It writes one labeled CSV per
   measurement into a session folder.
3. **Helper functions** appended at the end of the file (input parsing,
   CSV writing, grid coordinate math, session metadata).

The file is ~143 KB / ~4119 lines. About 96% of it is verbatim from
Keysight's `sweep.c`; the rest is the batch-mode patch.

---

## Installation (on the Linux machine)

You need `batch_sweep.c` in the **application/** folder of your installed
Hunter software (the same folder where `compile.sh` lives, next to
`sweep.c`).

```bash
# 1. Confirm you're in the right folder
cd ~/hunter/Internal_V2.5.7.0_x86/application/
ls sweep.c compile.sh        # both must be present

# 2. Copy batch_sweep.c into this folder (USB, scp, however)
ls batch_sweep.c             # confirm it landed
```

## Add to compile.sh

Open `compile.sh` and add this line **anywhere after** the existing
`sweep.c` gcc line (line 3):

```bash
gcc batch_sweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -fopenmp -o batch_sweep
```

(Use the exact same library flags as the `sweep.c` line — they're identical
on purpose, since `batch_sweep.c` is a derivative of `sweep.c`.)

Then rebuild:

```bash
./compile.sh
```

You should now have a `batch_sweep` executable next to `sweep`. If
compilation fails, see "Troubleshooting" below.

---

## Running a session

```bash
./batch_sweep
```

The program will:

1. **Ask you for session info** (model, antenna, object, operator, grid
   config, trial count, mode). Defaults are shown in `[brackets]`; press
   Enter to accept.
2. **Walk you through Keysight's normal setup prompts** (the same ones
   `./sweep` asks — about config, calibration, ports, etc.). For batch
   data collection you almost always want to:
   - Use current configuration: **Y**
   - Use default sweep setup (from `config.txt`): **Y**
   - Skip thermal stabilization: **N** (let it stabilize once)
   - Use multi-unit calibration as configured: **Y**
   - Disable everything optional you don't normally use
3. **Take a baseline sweep set** — empty container, `trialCount` sweeps.
4. **Loop through every position x every trial**, prompting you to place
   the object at each position. Type `0` to confirm placement, or `s`
   to skip.
5. **Exit cleanly** when done.

### Output layout

Each session creates a folder under `Data/`:

```
Data/
└── BreastPhantom_A2_MetalRod_20260603_1430/
    ├── session_metadata.txt
    ├── baseline_T01.csv
    ├── baseline_T02.csv
    ├── ... (one per baseline trial)
    ├── R2C2P1_T01.csv     <- row 2, col 2, top-left sub-position, trial 1
    ├── R2C2P1_T02.csv
    ├── R2C2P1_T03.csv
    ├── ...
    ├── R2C2P2_T01.csv     <- row 2, col 2, top-right
    ├── ...
    ├── R5C5P4_T16.csv     <- row 5, col 5, bottom-left, trial 16
```

Sub-position legend (matches your MATLAB script):
- **P1** = Top-Left
- **P2** = Top-Right
- **P3** = Bottom-Right
- **P4** = Bottom-Left

The CSVs themselves are in the **same format** Keysight's `sweep.c`
writes (Magnitude-Phase or Real-Imaginary depending on `config.txt`'s
`resultFormat`). Your existing analysis tooling that reads stock
sweep CSVs will read these unchanged.

### Session metadata file

`session_metadata.txt` contains everything you need to interpret the
folder later:

```
Hunter VNA Batch Sweep - Session Metadata
==========================================

Timestamp:  2026-06-03 14:30:12
Operator:   Peter
Model:      BreastPhantom_A2
Antenna:    SmallHoof75
Object:     MetalRod

Grid Configuration
  Total grid:    6 rows x 6 cols
  Measured rows: 2 3 4 5
  Measured cols: 2 3 4 5
  Cell size:     1.000 inches
  Divider thick: 0.250 inches

Measurement Plan
  Positions:           64
  Trials per position: 16
  Total sweeps:        1024 (+ 16 baseline)
  Mode:                INTERACTIVE
```

---

## What to expect at each prompt

After your session info, you'll hit Keysight's setup prompts from `sweep.c`.
Most of them you just answer Y/N. A typical run looks like:

```
Do you want to enable message logging [Y/N]? N
Do you want to continue with this configuration [Y/N]? Y
Do you want to enable the Ethernet Interface loss communication detection [Y/N]? N
Do you want to enable the Unit Monitoring [Y/N]? N
Do you want to re-construct the multi-unit FACTORY calibration ... [Y/N]? N
Do you want to enable multi-unit calibration factors to all units [Y/N]? Y
Do you want to perform sweep with the default setup [Y/N]? Y
Do you want to wait for thermal stabilization [Y/N]? N    (already warmed up)
Do you want to enable Port Segmentation Sweep [Y/N]? N
Do you want to calculate the active sweep time ... [Y/N]? N
```

Then a **single warmup sweep runs** (Keysight's setup always does one —
it overwrites `./Data/SPARAM_ReArrTest.csv` which we ignore). Then
`batch_sweep` takes over and runs:

```
=================================================
   BASELINE - remove all objects from container
=================================================
Press Enter when ready for 16 baseline sweep(s)...
```

...then prompts for each position.

---

## Reading the data back (Python)

Quick loader for a session folder:

```python
import glob, os, re
import pandas as pd
import numpy as np

def load_session(session_folder):
    """Returns dict: keys are 'baseline' and 'R<r>C<c>P<p>', values
    are numpy arrays of shape (numTrials, sweep_rows, sweep_cols)."""
    out = {}
    for csv_path in sorted(glob.glob(os.path.join(session_folder, '*.csv'))):
        name = os.path.basename(csv_path)
        m = re.match(r'(baseline|R\d+C\d+P\d+)_T(\d+)\.csv', name)
        if not m:
            continue
        key, trial = m.group(1), int(m.group(2))
        arr = pd.read_csv(csv_path, header=None).values
        out.setdefault(key, []).append((trial, arr))
    # Sort each key's trials and stack
    for k in out:
        out[k].sort(key=lambda x: x[0])
        out[k] = np.stack([a for _, a in out[k]], axis=0)
    return out

session = load_session('Data/BreastPhantom_A2_MetalRod_20260603_1430')
print(list(session.keys())[:5])
# ['baseline', 'R2C2P1', 'R2C2P2', 'R2C2P3', 'R2C2P4', ...]
print(session['R2C2P1'].shape)
# (16, num_freq_points, num_columns)
```

---

## Troubleshooting

### `./compile.sh` fails on the batch_sweep line

The compile.sh line MUST come AFTER the existing `sweep.c` compile line and
use the same library flags:

```bash
gcc batch_sweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -fopenmp -o batch_sweep
```

If you get `undefined reference to ...`, the most likely cause is a missing
library flag. Compare line-for-line against the `sweep.c` compile line in
your `compile.sh` — they should match except for the filename and `-o`
target.

### "Operator prompt accepts Enter but takes no measurement"

The Keysight setup prompts use `scanf` which can leave newlines in the
input buffer. If you hit the position prompt and the first one auto-skips,
type a literal `0<Enter>` (not just Enter) to confirm.

### Session folder name has weird characters

The session folder is built from `modelName` and `objectName` after stripping
anything that isn't `[A-Za-z0-9_-]`. Spaces become underscores. If you typed
`Breast Phantom A2`, the folder will be `BreastPhantomA2`. Use underscores
in your input if you want them preserved.

### `Data/` folder doesn't exist

`batch_sweep` will auto-create `Data/` and the session subfolder if they
don't exist. If the program errors with "Cannot open ... for writing", it
means you don't have write permission in the current directory — `cd` to
a folder you own (like your home directory) and re-run.

---

## Limits and known caveats

1. **No outlier detection in-loop.** Your MATLAB script flags outliers
   inside the session - `batch_sweep` does not. You'll need a post-hoc
   analysis script (the Python loader above is a starting point) to
   compute per-position trial variance and flag outliers.
2. **No on-the-fly redo/modify section.** If you bump a position mid-trial,
   you can either (a) skip the rest of that position with Ctrl-C (kills
   the program - you keep what's written so far) and re-run a targeted
   single-cell session, or (b) take a future small batch_sweep run with
   only the affected rows/cols and merge offline.
3. **One unit assumed.** The session metadata captures a single Hunter
   unit configuration. Multi-unit sessions still work (Keysight's
   setup logic handles it), but the metadata file doesn't break out
   per-unit serial numbers.
4. **AI-generated code.** `batch_sweep.c` was generated by Claude based on
   reading Keysight's `sweep.c` and `MN7021aApp.h`. The first compile may
   surface a small issue (missing include, wrong type, etc.) — paste the
   gcc error in your next Claude session and it should be a one- or
   two-line fix.

---

## Re-generating batch_sweep.c if Keysight updates sweep.c

`batch_sweep.c` is a patch of Keysight's `sweep.c`. If Keysight ships a new
version of `sweep.c` you want to incorporate, just ask Claude in a new
session: "regenerate batch_sweep.c from the current sweep.c using the same
patches as before" and reference this README. The patch points are:

- After `printf("Standard Sweep Program\n");`  — session setup block
- Replacing the `while(1) { ... }` repeat-the-sweep loop  — position x trial loop
- Appended at end of file  — helper functions

The function signature contract (parameters, globals like `segPort`,
`SParam1shm`, `SParam2shm` from `MN7021aApp.h`) is documented in this
README and the inline comments.
