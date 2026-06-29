# Phantom Calibration Tools

The final paper figure (`detectable_change/paper_figure.py`) overlays two things on top of the per-position scatter:

1. The adipose bowl and glandular insert outlines, traced from photos of the actual phantoms.
2. Hand-adjusted tumor dot positions, for cases where physically placing the tumor surrogate in a glandular configuration didn't end up exactly on the grid corner.

This folder contains the interactive Python tools used to produce both. **You only need to run these if you're working with new phantom photos or if you want to redo the existing calibration**; the constants from the original calibration are already baked into `paper_figure.py` and `position_adjustments.json`.

## Requirements

- Python 3.x
- `numpy`, `scipy`, `matplotlib`, `Pillow` (`PIL`), `tkinter`

Tkinter ships with the standard Python installer on Windows. On Linux you may need `apt install python3-tk`.

## The Three Tools

### Step 1: `click_calibration.py`

A drag-and-drop tkinter app that opens each phantom photo in turn and lets you mark:

- **9 grid intersection points** (always required) at known inch coordinates `(1,1), (5,1), (5,5), (1,5), (2,2), (3,3), (4,4), (2,4), (4,2)`. You drag 9 preplaced green markers onto the photo's grid intersections. This establishes the pixel-to-inch transform.
- **Bowl outline points** (first photo only by default). You click as many points as you want around the adipose bowl edge.
- **Glandular outline points** (F4 and F5 photos). You click as many points as you want around each glandular insert edge.

Keyboard shortcuts inside the app:

- `n` — go to the next stage / photo
- `u` — undo last click (only during the click stages, not during the calibration-marker drag)

The output is `calibration/calibration.json`, containing all of the pixel coordinates you clicked.

To run:

```bash
cd detectable_change/calibration
python click_calibration.py
```

The three phantom photos are in `phantom_photos/`. To calibrate **new** phantoms, drop their `.jpg` files into `phantom_photos/` and edit the `PHOTOS` list near the top of `click_calibration.py`.

### Step 2: `apply_calibration.py`

A non-interactive script that consumes `calibration.json` and produces the actual outline constants. It:

- Fits a 2x3 affine transform from your 9 grid clicks to the known inch coordinates.
- Applies that transform to convert every bowl and glandular click from pixels to inches.
- Fits an algebraic least-squares ellipse to the bowl click points (typical residual ≈ 2.6% of mean radius).
- Smooths each glandular outline through angle-binned periodic cubic-spline resampling.
- Prints the resulting `BOWL_ELLIPSE_CENTER / RX / RY`, `F4_OUTLINE`, and `F5_OUTLINE` constants to stdout, ready to paste into `paper_figure.py`.

To run:

```bash
cd detectable_change/calibration
python apply_calibration.py
```

The script does not write anywhere; copy the printed constants into `paper_figure.py` to update the overlays.

### Step 3: `adjust_positions.py`

A drag-and-drop tkinter app that, for each phantom configuration:

- Loads the matching phantom photo.
- Reads the per-position measurement coordinates from `../results/detectable_diff_<config>.npz`.
- Uses the calibration in `calibration.json` to draw each measurement dot on top of the photo at its computed grid corner.
- Lets you drag any dot to the spot where you physically placed the tumor surrogate during recording.

Keyboard shortcuts:

- `n` — go to the next configuration
- `s` — save the current overrides to `../position_adjustments.json` (overwrites). The save happens automatically when you advance with `n`, but `s` lets you save mid-config.

The output is `detectable_change/position_adjustments.json` (one level up), which `paper_figure.py` reads to shift the affected dots in the final figure.

To run:

```bash
cd detectable_change/calibration
python adjust_positions.py
```

## Typical Workflow

If you only want to add or recalibrate one phantom configuration:

1. Drop the annotated photo into `phantom_photos/`.
2. Run `click_calibration.py`, calibrate the grid + outline points for that photo, save.
3. Run `apply_calibration.py`, copy the new constants into `paper_figure.py`.
4. Run `adjust_positions.py` to fine-tune individual tumor dot positions (optional).
5. Run `../paper_figure.py` to re-render the figure with the updated overlays.

If you want to recalibrate **all three** phantoms from scratch, run `click_calibration.py` once and step through all three photos in sequence (`n` to advance).

## Notes

- The 9-point grid calibration uses a small over-determined system so the fit is robust if a click is slightly off. You don't need to be pixel-perfect on the grid markers; just close.
- The phantom photos in `phantom_photos/` are the ones the paper figure was built from. You can replace them with sharper or newer photos; just keep the filenames (`A2_Annotated.jpg`, `A2F4_Annotated.jpg`, `A2F5_Annotated.jpg`) or update the `PHOTOS` list in `click_calibration.py` and `adjust_positions.py`.
- `calibration.json` already contains the click data from the original paper calibration, so `apply_calibration.py` will reproduce the constants already in `paper_figure.py` without you re-clicking anything.
