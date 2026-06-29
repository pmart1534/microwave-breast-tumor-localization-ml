# two-antenna-mwi-cnn

Code and data for the paper:

> **Two-Antenna Microwave Breast Tumor Localization Using a Convolutional Neural Network**
> Peter Martin, Mouad Addad, Sam Makin, Cynthia M. Furse
> *IEEE Journal of Electromagnetics, RF, and Microwaves in Medicine and Biology*, 2026 (submitted).

This repository contains the raw S-parameter measurement data, the MATLAB scripts used to record the data and train the hierarchical CNN, and the Python scripts used to generate the detectable-change analysis (Fig. 4 of the paper).

## Repository Layout

```
datasets/                            Raw VNA measurements (5 .mat files)
  A2_Empty/                          Adipose-only phantom (2 sessions, 16 trials/pos)
  A2_F4/                             A2 + medium glandular insert (1 session, 16 trials/pos)
  A2_F5/                             A2 + largest glandular insert (2 sessions, 16 + 28 trials/pos)

matlab/
  data_recording/                    VNA acquisition over the inner 4x4 grid
    Inner4x4_DataRecording.m
  cnn_training/                      Two-stage hierarchical classifier
    Hierarchical_Classification_ML.m

detectable_change/                   Python detectable-change analysis (Fig. 4)
  detectable_difference.py           Computes per-position Z(p) in dB from the .mat files
  parse_accuracy_txt.py              Converts MATLAB SpatialAcc_*.txt → CSV format
  paper_figure.py                    Renders the final Fig. 4 (uses outputs of the two above)
  position_adjustments.json          Hand-adjusted tumor dot positions for the glandular layouts
  accuracy_data/                     Per-position CNN accuracy CSVs (used for dot sizes)
  results/                           Pre-computed .npz / .csv outputs from detectable_difference.py
  figures/                           Output PNGs
  calibration/                       Interactive Tk tools for re-tracing phantom outlines
                                     and adjusting tumor dot positions on photos
```

## Datasets

Each `.mat` file holds one complete recording session. For every measured grid position, the VNA captured `N` repeated sweeps of all four complex S-parameters (S11, S21, S12, S22) at 201 frequency points from 300 kHz to 6.42 GHz. Each trial is stored as an `8 x 201` matrix (magnitude and phase of all four S-parameters), together with the empty-phantom baseline, the frequency axis, and a `gridConfig` struct describing how the recording was laid out.

The data-recording program (`matlab/data_recording/Imager_DataRecording.m`) supports flexible grid configurations — preset options (Butter Container, Breast Phantom) plus a fully configurable Custom mode. The files supplied here all happen to use the same configuration the J-ERM paper used: a **6x6 grid with the inner 4x4 measured** (rows 2–5, columns 2–5), with four corner sub-positions per cell, giving up to 64 candidate measurement positions per session. The CNN training script (`matlab/cnn_training/Hierarchical_Classification_ML.m`) is specialized for this inner-4x4 layout; see its README for details.

| Folder | Sessions | Trials per position | Notes |
|---|---|---|---|
| `A2_Empty/` | 2 | 16 | Adipose-only A2 shell filled with canola oil |
| `A2_F4/` | 1 | 16 | Medium fibroglandular insert; position R4C2P1 excluded for the detectable-change plot (direct coupling artifact) |
| `A2_F5/` | 2 | 16, 28 | Largest fibroglandular insert; the configuration that exposes the live-prediction failure mode discussed in Section IV |

## Requirements

- **MATLAB R2020a or later** with Deep Learning Toolbox, Statistics and Machine Learning Toolbox, and Instrument Control Toolbox (for the VNA acquisition). See `matlab/data_recording/README.md` and `matlab/cnn_training/README.md` for details.
- **Python 3.8 or later** with `numpy`, `scipy`, `matplotlib`, and `Pillow` (the latter only needed for the calibration tools). The Python scripts live under `detectable_change/`; install their requirements with:
  ```bash
  pip install -r detectable_change/requirements.txt
  ```

## How to Reproduce

1. **CNN training (MATLAB).** Open `matlab/cnn_training/Hierarchical_Classification_ML.m`, point the data path at one of the `datasets/` folders, and run. The script performs the random hyperparameter search described in Table I and saves the trained Stage 1 and Stage 2 models.
2. **Detectable-change analysis (Python).** From `detectable_change/`, run `python paper_figure.py` to render Fig. 4 using the pre-computed `results/` and `accuracy_data/` already in the repo. To regenerate the intermediate results from scratch, see `detectable_change/README.md` for the full step-by-step pipeline (raw `.mat` → `detectable_difference.py` → `.npz`, MATLAB `SpatialAcc_*.txt` → `parse_accuracy_txt.py` → CSV, then `paper_figure.py`). For re-tracing the phantom outlines on new photos, see `detectable_change/calibration/README.md`.

## Acknowledgments

- 3D-printed breast phantom shells from the University of Manitoba.
- Flexible monopole antennas originally designed at McGill and Laval Universities.
- All code in this repository was generated with assistance from Claude (Anthropic) and reviewed and validated by the first author.

## Citation

Pending publication.
