# Detectable-Change Analysis

This folder produces the final detectable-change figure from the paper (Fig. 4). It also contains the helper tools used to build the per-position CNN-accuracy CSVs and the phantom-outline calibration that the figure overlays.

## Requirements

Python 3.8 or later with:

- `numpy`
- `scipy`
- `matplotlib`

The calibration tools (in `calibration/`) additionally need `Pillow` (`PIL`) and `tkinter`. See `calibration/README.md`.

Install everything for this folder in one shot from the repo root:

```bash
pip install -r requirements.txt
```

## Pipeline at a Glance

```
       (1) detectable_difference.py         (2) parse_accuracy_txt.py
   ┌──────────────────────────────┐    ┌─────────────────────────────────┐
   │ datasets/A2_*/*.mat          │    │ SpatialAcc_*.txt                │
   │     ↓                        │    │  (produced by the MATLAB         │
   │ results/detectable_diff_*.npz│    │  CNN training script)            │
   └──────────────┬───────────────┘    │     ↓                            │
                  │                    │ accuracy_data/                   │
                  │                    │   per_position_accuracy_*.csv    │
                  │                    └────────────────┬─────────────────┘
                  │                                     │
                  ↓                                     ↓
        ┌──────────────────────────────────────────────────────┐
        │              (3) paper_figure.py                     │
        │  combines DD .npz + accuracy CSV + position_         │
        │  adjustments.json + hard-coded phantom outlines      │
        │  →  figures/paper_figure.png                         │
        └──────────────────────────────────────────────────────┘
```

The two inputs to `paper_figure.py` come from two independent pipelines:

- **Detectable change (color of each dot)** comes from `detectable_difference.py`, which reads the raw VNA `.mat` files in `../datasets/` and computes per-position `Z(p)` in dB.
- **CNN accuracy (size of each dot)** comes from the MATLAB CNN training script `matlab/cnn_training/Hierarchical_Classification_ML.m`, which exports a `SpatialAcc_WithinSession_*.txt` file. `parse_accuracy_txt.py` converts that text file into the CSV format `paper_figure.py` reads.

## Files

| File | What it does |
|---|---|
| `detectable_difference.py` | Reads `../datasets/A2_*/*.mat`, computes the 95% CI gap per frequency, aggregates to per-position `Z(p)` in dB, writes `results/detectable_diff_*.npz` + `.csv`. Also produces a basic 3x2 panel figure at `figures/fig_dd_panel.png`. |
| `parse_accuracy_txt.py` | Parses `SpatialAcc_WithinSession_*.txt` files produced by the MATLAB training (Section 8B exports them) into `accuracy_data/per_position_accuracy_*.csv`. Searches `../datasets/<config>/` by default; override the location with the `SPATIALACC_DIR` environment variable. |
| `paper_figure.py` | Renders the final Fig. 4 figure into `figures/paper_figure.png`. Reads everything from the local folders, so no other scripts need to be running. |
| `position_adjustments.json` | Hand-tuned per-position overrides used by `paper_figure.py` to shift tumor dots to their measured physical positions when the default grid coordinates don't match the photo. Edit it via the `calibration/adjust_positions.py` GUI. |
| `accuracy_data/` | Per-position CNN accuracy CSVs (one per phantom configuration). |
| `results/` | Pre-computed `.npz` and `.csv` outputs from `detectable_difference.py`. |
| `figures/` | Output PNGs. |
| `calibration/` | Interactive Python tools for tracing the adipose bowl and glandular insert outlines on phantom photos, and for adjusting tumor dot positions. See `calibration/README.md`. |

## How to Reproduce the Figure

The fast path, using the data and CSVs already in this repo:

```bash
python paper_figure.py
```

That single command reads everything from the local `results/`, `accuracy_data/`, and `position_adjustments.json` files and writes `figures/paper_figure.png`. No other scripts need to run first.

## How to Regenerate from Scratch

If you want to rebuild every intermediate output from the raw data:

1. **Detectable-change values**

   ```bash
   python detectable_difference.py
   ```

   Reads `../datasets/A2_Empty/*.mat`, `../datasets/A2_F4/*.mat`, `../datasets/A2_F5/*.mat`. Writes `results/detectable_diff_A2_Empty.npz`, `.csv`, and the same for F4 and F5.

2. **CNN-accuracy CSVs** (only needed if you retrain the CNN)

   First run `matlab/cnn_training/Hierarchical_Classification_ML.m` through Section 8B. That writes a `SpatialAcc_WithinSession_*.txt` file alongside the input `.mat`. Then:

   ```bash
   python parse_accuracy_txt.py
   ```

   This converts the `.txt` to `accuracy_data/per_position_accuracy_*.csv`. By default it searches `../datasets/<config>/` for the SpatialAcc text files; if your MATLAB output went elsewhere, set `SPATIALACC_DIR` to that folder before running.

3. **(Optional) Re-calibrate phantom outlines**

   The bowl ellipse and F4/F5 outlines in `paper_figure.py` are hard-coded constants traced from the photos in `calibration/phantom_photos/`. If you have new phantom photos, see `calibration/README.md` for the interactive workflow.

4. **(Optional) Adjust tumor dot positions**

   `paper_figure.py` reads `position_adjustments.json` and shifts individual dots to their hand-marked locations. To regenerate this file for new phantoms, use the GUI in `calibration/adjust_positions.py` (see `calibration/README.md`).

5. **Final figure**

   ```bash
   python paper_figure.py
   ```

## Notes on Reproducing the Exact Paper Image

The CSVs in `accuracy_data/` reflect the *current* state of CNN training. Because the MATLAB training script uses a 75/25 stratified train/test split with a randomized seed, different training runs will end up with slightly different positions in the held-out test set — which means a slightly different number of dots displayed (positions without test samples are dropped). The science is unchanged; only which specific positions happen to have a CNN accuracy value can differ between training runs.

If you need to match the exact figure from the paper, you would need the snapshot of these CSVs that existed when the paper was finalized.
