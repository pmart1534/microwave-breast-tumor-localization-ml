# Imager Data Recording — User Guide

## Overview

This program records S-parameter measurements from a Vector Network Analyzer (VNA). It measures complex S-parameters (magnitude + phase) at each frequency point for multiple grid positions.

The program supports three measurement models:

1. **Butter Container** — 6x6 grid, inner 4x4 measured
2. **Breast Phantom** — user-defined grid and measurement area
3. **Custom** — fully configurable with auto-centering option

## Requirements

- MATLAB R2020a or later
- Instrument Control Toolbox (for `visadev`)
- A Keysight (or compatible) VNA connected via LAN or USB

## Finding and Connecting to Your VNA

1. Open MATLAB **with the VNA powered on**.
2. Run: `visadevlist`
3. This shows all connected instruments. Look for your VNA. Common address formats:
   - **TCPIP**: `TCPIP0::192.168.1.100::hislip0::INSTR`
   - **USB**: `USB0::0x2A8D::0x5C18::MY12345678::INSTR`
   - **Local**: `TCPIP0::localhost::hislip0::INSTR` (if MATLAB is on the same computer as the VNA software)
4. Copy this address — you will enter it when the program asks.

If `visadevlist` returns nothing:

- Check that the VNA is powered on and connected.
- Check that NI-VISA or Keysight IO Libraries are installed.
- Try `instrhwinfo('visa')` for more details.

## VNA Setup

Before running the program, set up your VNA:

1. Set the frequency range (e.g., 300 kHz to 6.42 GHz).
2. Set the number of points (e.g., 201).
3. Create traces for **all four** S-parameters on Channel 1 (S11, S21, S12, S22). The program auto-detects trace names, so any naming is fine.
4. Make sure the VNA is actively sweeping (continuous mode).

## Measurement Models

### Butter Container

- 6x6 total grid, measures inner 4x4 (rows 2-5, cols 2-5).
- Outer cells excluded due to antenna proximity effects.
- 1-inch cells, 0.25-inch dividers.
- 16 cells × 4 corners = 64 positions.

### Breast Phantom

- You specify total grid dimensions (rows and columns).
- You specify which rows and columns to measure.
- You specify cell size and divider thickness.
- You enter a phantom version ID (e.g., A2, F3) and optionally a glandular version ID.
- Grid settings can be saved per-phantom so different phantoms can have different grid sizes.

### Custom

- Fully configurable grid dimensions.
- Auto-centering option for even measurement counts (e.g., 6 total rows, measure 4 = auto-selects rows 2-5).
- Manual row/column selection for odd counts.
- Custom cell size and divider thickness.

## Saved Configurations

The program remembers your previous setups in `saved_configs.mat` (in the program folder). It will offer to save and reuse:

- Custom model definitions (grid + measurement area)
- Custom antenna names
- Custom object names
- Phantom version IDs and their grid settings
- Glandular version IDs
- Per-model skip lists (positions you do not measure)

Anything you save shows up as a numbered option the next time you run the program.

## Recording Modes

Before the baseline step, the program asks which recording mode you want. This choice applies to both the baseline measurements and the per-position data collection.

### A. Automatic mode

- All measurements at a position are taken back-to-back with a fixed delay between sweeps (default 0.2 seconds, configurable when you start).
- You only have to confirm placement once per position (type `0`), then the program takes all trials by itself.
- Best for fast data collection when you do not need to verify each individual sweep.

### B. Interactive mode (original behavior)

- You press Enter before every single measurement.
- Best for careful data collection where you want to confirm or inspect each sweep individually.

Either mode can be picked at the start of a run. The baseline section follows the same mode you select.

## Step-by-Step Guide

Run the program section by section (Ctrl+Enter in MATLAB).

1. **Section 1 — Configuration**
   - Select your measurement model (Butter Container, Breast Phantom, Custom, or a previously saved model).
   - Select antenna type (built-in or a saved custom antenna).
   - Select the object you are placing (Metal Rod, Metal Marble, a saved custom object, or enter a new one).
   - Enter your name (operator).
   - Enter number of measurements per point (10–16 recommended).

2. **Section 2 — Grid Setup**
   - The grid positions are automatically calculated.
   - Review the position list to verify it is correct.

3. **Section 3 — VNA Connection**
   - Enter your VNA address (or press Enter for default).
   - The program will connect, auto-detect traces, and read the frequency axis.
   - Verify the frequency range and number of points.

4. **Section 4 — Baseline**
   - Choose Automatic or Interactive mode (applies to data collection too).
   - Remove all objects from the container; only the medium (oil, etc.) should be present.
   - Take baseline measurements (same count as regular ones).

5. **Section 5 — Data Collection**
   - The program walks you through each position.
   - For each position: type `0` and press Enter to confirm placement, or type `s` to skip.
   - Automatic mode: after confirming, all trials are taken automatically with the chosen delay between sweeps.
   - Interactive mode: press Enter for each measurement.
   - A progress counter shows which position you are on.
   - If a saved skip list exists for the selected model, the program offers to auto-skip those positions.

6. **Section 6 — Save**
   - Choose where to save the `.mat` file.
   - The file contains all measurements, baseline, frequency axis, and grid information.

### Optional Sections

7. **Section 7 — Quick Visualization** (plots sample vs baseline)
8. **Section 8 — Outlier Detection** (finds unusual measurements)
9. **Section 9 — Redo / Modify Measurements**
   - Retake measurements for a specific cell, or mark a cell as skipped (sets it to `NaN`).
   - Works on data in memory or on a saved `.mat` file.

## Position Navigation

For each grid position, you will see:

```
POSITION 15 of 64: Row 3, Col 4, Top-Left (Corner 1)
  Physical location: (3.13, 2.13) inches
```

- Type `0` and press Enter to confirm the object is placed.
- Type `s` and press Enter to skip the position (stored as `NaN`).
- Interactive mode: press Enter for each measurement within that position.
- Automatic mode: all measurements happen automatically after the `0` confirmation.
- The `0` requirement prevents accidental position advances.

Sub-positions within each cell:

- **P1** = Top-Left corner
- **P2** = Top-Right corner
- **P3** = Bottom-Right corner
- **P4** = Bottom-Left corner

## VNA Trace Auto-Detection

The program automatically queries your VNA for all configured traces using the `:CALC1:PAR:CAT?` command. It parses the response to find trace names and their S-parameter types. This means:

- You do not need to hardcode trace names.
- Any trace naming convention works.
- The program adapts to however many traces are configured.

## Tips

- 10–16 measurements per point gives a solid statistical sample.
- Take a fresh baseline if you move the antennas or change the oil level.
- Save frequently — if MATLAB crashes, unsaved data is lost.
- For combined datasets: take measurements on different days for temporal diversity.
- If the VNA times out, increase `vna.Timeout` in the code.
- Automatic mode is much faster but does not give you a chance to react between sweeps — make sure placement is stable before confirming with `0`.

## Data Format

The saved `.mat` file contains:

| Variable | Description |
|---|---|
| `data` | Cell array `[numPositions x (1 + trialCount)]`. Column 1 is the position label (e.g., `R2C3P1`). Columns 2+ are each `numSParamRows x numFreqPoints` matrices. |
| `baseline` | `numSParamRows x numFreqPoints` (averaged empty) |
| `baselineAll` | `numSParamRows x numFreqPoints x trialCount` (all individual baseline sweeps) |
| `freq` | `1 x numFreqPoints` (frequency axis in Hz) |
| `xyCoords` | `numPositions x 2` (physical x,y in inches) |
| `posLabels` | Cell array of position label strings |
| `positions` | Table with columns `GridRow`, `GridCol`, `SubPos`, `SubPosName` |
| `gridConfig` | Struct: `modelName`, `gridRows`, `gridCols`, `measureRows`, `measureCols`, `cellSizeInch`, `dividerInch`, `objectName`, `operatorName`, `sessionTimestamp` (plus `phantomVersion` / `glandularVersion` for the Breast Phantom model) |
| `traceList` | `Nx2` cell array of auto-detected VNA traces (catalog name, S-parameter type) |
| `antennaName` | String describing the antenna used |
| `objectName` | String describing the object placed |
| `operatorName` | Name of the person taking measurements |
| `sessionTimestamp` | Date/time the session started |
| `gridRows` | Number of grid rows (e.g., 6) |
| `gridCols` | Number of grid columns (e.g., 6) |
| `gridSizeInches` | Physical size of the grid in inches |
| `trialCount` | Number of measurements per position |
| `numFreqPoints` | Number of frequency points |
| `numSParamRows` | Number of rows per measurement matrix |
| `skippedPositions` | Logical vector marking skipped positions |

For 4 S-parameters (the standard configuration), the rows of each measurement matrix are:

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

## Combining Multiple Sessions

Use `Imager_DataCombiner.m` to merge multiple `.mat` files into one larger dataset. The combiner validates that all files have matching frequency points, S-parameter row counts, and position labels.

## Troubleshooting

**VNA connection fails**
- Check `visadevlist` output.
- Verify the VNA is in remote/LAN mode.
- Try USB connection if LAN fails.

**Timeout during measurement**
- Increase `vna.Timeout` (default 60 seconds).
- Reduce number of frequency points on VNA.
- Check that VNA is in continuous sweep mode.

**All measurements look the same**
- Verify the object is actually in the medium.
- Check that antennas are connected and positioned correctly.
- Compare with baseline — there should be visible differences.

**Outlier detection flags many trials**
- You may have forgotten to move the object between positions.
- In Automatic mode, the delay may be too short for stable sweeps — try increasing it.
- Use Section 9 (Redo) to retake affected cells.
- Re-save after redoing measurements.

## AI Acknowledgment

This code was fully generated by Claude (Anthropic, claude.ai) with inputs from Peter Martin.
