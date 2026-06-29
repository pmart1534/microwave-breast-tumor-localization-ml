# Hierarchical Classification ML — User Guide

## Overview

This program trains a two-stage hierarchical CNN that classifies the position of a metal scattering object from S-parameter measurements.

- **Stage 1 — Quadrant classifier.** One CNN classifies each measurement into one of four quadrants: TL, TR, BL, BR.
- **Stage 2 — Position classifier.** Four separate CNNs (one per quadrant) classify the precise grid position within that quadrant.

Splitting the problem this way is faster and more accurate than a single flat classifier on all 64 positions, because each individual network only has to distinguish among ~16 nearby positions.

> **Grid assumption.** This script is hard-coded for a **6x6 grid with the inner 4x4 measured** (rows 2–5, columns 2–5), with the inner 4x4 split into four 2x2 quadrants. If your data was recorded with a different layout, this specific script will not work as written — Section 0 (Configuration) defines the quadrant boundaries explicitly. The companion data-recorder is flexible across grid layouts; this trainer is specialized for the inner-4x4 case used in the paper.

## Requirements

- MATLAB R2020a or later
- Deep Learning Toolbox (for `trainNetwork`, CNN layers)
- Statistics and Machine Learning Toolbox (used for the optimization variable declarations in Section 5B)
- Optional: Parallel Computing Toolbox (for GPU training)
- Optional: NVIDIA GPU (significantly speeds up training)

## Check GPU Availability

Run in the MATLAB command window:

```matlab
gpuDeviceCount    % returns 1 if a GPU is available, 0 if not
gpuDevice         % shows GPU details
```

Training on GPU is 5–20x faster than CPU for these networks.

## Important: Training Performance Note

The lab computers (e.g. Microwave Lab PCs) typically do **not** have dedicated GPUs and have limited processing power. Training the CNN models on these machines can take significantly longer (potentially hours instead of minutes).

**Recommended workflow:**

1. Use the lab computer only for data recording (connecting to the VNA and taking measurements).
2. Save the `.mat` data file to a USB drive or cloud storage.
3. Transfer the data to a personal computer with a GPU (NVIDIA GTX/RTX series) for training and optimization.
4. Save the trained model (`.mat` file) on the faster computer.
5. Transfer the trained model back to the lab computer for live prediction. Live prediction does **not** need a GPU — it only runs one measurement at a time.

## Input Data Format

The CNN treats each measurement as an `8 x numFreqPoints x 1` matrix:

| Row | Content |
|---|---|
| 1 | `|S11|` (dB) |
| 2 | `angle(S11)` (radians) |
| 3 | `|S21|` (dB) |
| 4 | `angle(S21)` (radians) |
| 5 | `|S12|` (dB) |
| 6 | `angle(S12)` (radians) |
| 7 | `|S22|` (dB) |
| 8 | `angle(S22)` (radians) |

`numFreqPoints` is read directly from whatever recording file you load — there is no need to set it manually.

## Step-by-Step Guide

Run the program section by section (Ctrl+Enter).

1. **Section 0 — Configuration**
   - Defines the four quadrant boundaries (TL, TR, BL, BR) over the inner 4x4 grid.
   - Sets the tunable CNN parameters listed below.
   - Auto-detects (or prompts for) the container photo used by the spatial accuracy maps and heatmap views in later sections.

2. **Section 1 — Load Training Data**
   - Prompts you for the `.mat` recording file produced by `Imager_DataRecording.m` (or a combined dataset).
   - Reads `data`, `baseline`, `freq`, `posLabels`, etc.

3. **Section 2 — Build Features and Labels**
   - Parses position labels in `R#C#P#` format.
   - Builds the training matrices with baseline subtraction.
   - Assigns each measurement a quadrant label for Stage 1.

4. **Section 3 — Split Data**
   - 75/25 train/test split, stratified by quadrant.
   - Random seed fixed for reproducibility.

5. **Section 4 — Train Stage 1 (Quadrant Classifier)**
   - Trains a 4-class CNN over the four quadrants.
   - Typically reaches near 100% accuracy quickly because the inter-quadrant separation is large.

6. **Section 5 — Train Stage 2 (Per-Quadrant Position Classifiers)**
   - Trains four separate CNNs, one per quadrant, each over the ~16 positions inside that quadrant.

7. **Section 5B — Auto-Optimize Hyperparameters (Optional)**
   - Random search over learning rate, mini-batch size, conv filter counts, fully-connected neurons, and dropout. Each trial trains a short CNN and measures held-out accuracy.
   - The search **terminates early** as soon as a trial hits 100% accuracy. The on-screen prompt currently reads "Bayesian optimization" for historical reasons; the underlying code is random search (early-termination support is the reason random search was chosen).
   - Per-stage trial budgets: `optimTrials_Stage1` (default 10) for Stage 1, `optimTrials_Quadrant` (default 25) per Stage 2 quadrant.

8. **Section 6 — Save Models**
   - Saves Stage 1 + all Stage 2 networks plus the baseline, frequency axis, and grid metadata into a single `.mat` model file.

9. **Section 7 — Load Models**
   - Reloads a previously saved model file so you can skip retraining and jump straight to evaluation or live prediction.

10. **Section 8 — Evaluate (Confusion Matrices)**
    - Five confusion matrices: one for the Stage 1 quadrant decision, plus one per Stage 2 quadrant.
    - Navy/teal color scheme with percentage labels.

11. **Section 8A — Quadrant Spatial Accuracy Map**
    - Overlays Stage 1 quadrant-prediction accuracy on top of the container photo.

12. **Section 8B — Position Spatial Accuracy Map**
    - Overlays Stage 2 per-position accuracy on the container photo, color-coded by accuracy with red arrows showing the direction of the most common error.
    - White = 100%, Teal = 80–99%, Orange = 50–79%, Red = below 50%.

13. **Section 9 — Feature Importance Analysis**
    - Ablation study showing how accuracy drops when each S-parameter (or its magnitude/phase component) is removed.
    - PCA visualization showing how well the data clusters by quadrant or position.

14. **Section 10 — Heatmap Visualization**
    - Per-position confidence heatmap rendered on top of the container photo for visualizing how confident the model is across the grid.

15. **Section 11 — Diagnostic Single-Position Test (VNA)**
    - Connects to the VNA, picks a random subset of positions for you to physically place the object at, and reports per-position accuracy. Useful sanity check before going live.

16. **Section 12 — Live Prediction (VNA)**
    - Continuous real-time prediction from the VNA: sweep → baseline-subtract → Stage 1 → Stage 2 → display.
    - Rolling average smooths the displayed prediction over the last `rollingAvgWindow` sweeps (default 5).
    - Fresh baseline option before starting.
    - Close the figure window to stop.

## Tunable Parameters (Section 0)

### Stage 1 (Quadrant Classifier)

| Parameter | Description | Default |
|---|---|---|
| `stage1_LR` | Initial learning rate | `1e-3` |
| `stage1_BatchSize` | Samples per batch | `16` |
| `stage1_Epochs` | Training epochs | `10` |
| `stage1_Conv1Filters` | First conv layer filters | `32` |
| `stage1_Conv2Filters` | Second conv layer filters | `32` |
| `stage1_FC1Neurons` | Fully connected neurons | `64` |
| `stage1_Dropout` | Dropout rate | `0.3` |
| `stage1_LRDropFactor` | LR reduction factor | `0.5` |
| `stage1_LRDropPeriod` | Epochs between LR drops | `5` |

### Stage 2 (Per-Quadrant Position Classifiers — same params apply to all 4)

| Parameter | Description | Default |
|---|---|---|
| `stage2_LR` | Initial learning rate | `1e-3` |
| `stage2_BatchSize` | Samples per batch | `16` |
| `stage2_Epochs` | Training epochs | `100` |
| `stage2_Conv1Filters` | First conv layer filters | `32` |
| `stage2_Conv2Filters` | Second conv layer filters | `32` |
| `stage2_FC1Neurons` | Fully connected neurons | `64` |
| `stage2_Dropout` | Dropout rate | `0.3` |
| `stage2_LRDropFactor` | LR reduction factor | `0.5` |
| `stage2_LRDropPeriod` | Epochs between LR drops | `30` |

### Optimizer (Section 5B)

| Parameter | Description | Default |
|---|---|---|
| `optimTrials_Stage1` | Number of random-search trials for Stage 1 | `10` |
| `optimTrials_Quadrant` | Number of random-search trials per Stage 2 quadrant | `25` |

### Live Prediction

| Parameter | Description | Default |
|---|---|---|
| `rollingAvgWindow` | Average last N predictions on screen | `5` |

## CNN Architecture (Both Stages)

Both stages use the same 14-layer sequence; only the number of classes at the final fully connected layer differs (4 for Stage 1, up to 16 for Stage 2). The architecture is hardcoded in Sections 4 and 5; the only parameters Section 0 exposes are the filter / neuron counts.

```
imageInputLayer([8 numFreqPoints 1], 'Normalization', 'zscore')
convolution2dLayer([4 20], conv1_filters, 'Padding','same')   →  bn  →  relu
convolution2dLayer([2 10], conv2_filters, 'Padding','same')   →  bn  →  relu
fullyConnectedLayer(fc1_neurons)                              →  bn  →  relu
dropoutLayer(dropout_rate)
fullyConnectedLayer(num_classes)
softmaxLayer
classificationLayer
```

## Saved Model Format

The `.mat` model file written by Section 6 contains:

| Variable | Description |
|---|---|
| `coarseNet` | Stage 1 quadrant classifier |
| `quadrantNets` | Cell array of 4 Stage 2 networks |
| `positionLabelsPerQuad` | Position labels for each quadrant |
| `positionCoordsPerQuad` | Physical (x,y) coords for each quadrant |
| `baseline` | Reference baseline measurement |
| `freq` | Frequency axis (Hz) |
| `numFreqPoints` | Number of frequency points |
| `numSParamRows` | Rows per measurement matrix |
| `traceList` | VNA trace names (used by the live-prediction section) |
| `gridRows`, `gridCols` | Grid dimensions |
| `cellSizeInch` | Cell size in inches |
| `measureRows`, `measureCols` | Which rows / columns were measured |

## Tips for Better Results

- More data from different sessions beats more data from one session. Use a data combiner to merge multiple recording sessions before training.
- Take a fresh baseline right before live testing.
- If live results are poor but training accuracy is high, baseline drift is the likely cause.
- The Section 5B random search will stop early if it hits 100% — that is the expected behavior.
- If training accuracy plateaus low, try increasing epochs or adjusting the learning rate manually before reaching for the optimizer.

## Compatibility

This program loads data from:

- `Imager_DataRecording.m` (any model type that produces the standard `.mat` layout)
- Legacy files from older recorders. Files without a `gridConfig` struct are assumed to be 6x6 grids with inner 4x4 measurement area.

The program auto-detects the number of S-parameter rows from the data, so it works with any number of VNA traces as long as the row ordering follows the magnitude/phase convention shown above.

## AI Acknowledgment

This code was fully generated by Claude (Anthropic, claude.ai) with inputs from Peter Martin.
