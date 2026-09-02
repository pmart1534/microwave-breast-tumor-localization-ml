# A3 Hunter detectable-change figures (MAX-overlay)

Adapts the A2 detectable-change figure (`../`) to the **A3 phantom** on the
**4-port Hunter VNA**, sizing the dots by the **LOSO** accuracy from the
CNN-vs-MLP study (`../../../../CNN vs MLP/`).

One panel per config (A3 empty / A3+F4 / A3+F5). A single **antenna mode** makes
each figure internally consistent — the DD color, the accuracy, and the antenna
markers all use the SAME antennas:

| mode | ports | DD color (max over) | dot size (LOSO acc) | markers |
|---|---|---|---|---|
| `single1` | 1 | S11 | antenna-1 (S11) | {1} |
| `pair13` | 1,3 | max S11/S31/S33 | 1&3 pair (refl+trans) | {1,3} |
| `all` | 1,2,3,4 | max over all 10 unique S | full array (refl+trans) | {1,2,3,4} |
| `refl_pair13` | 1,3 | max S11/S33 | 1&3 **reflection only** | {1,3} |
| `refl_all` | 1,2,3,4 | max S11/S22/S33/S44 | all-4 **reflection only** | {1,2,3,4} |

`refl_*` modes use ONLY reflection S-parameters (Sii) — no transmission — for
both the DD color and the LOSO accuracy.

- **Color** = MAX-overlay detectable change `Z(p)` in dB over the mode's
  S-parameters (band-mean linear CI-gap Δ → 20·log10; detdifplot.py's `Max`).
- **Size** = that mode's per-position LOSO accuracy.
- **Overlays** = numbered antenna markers (only the mode's antennas) + the
  adipose bowl and glandular insert outlines.

Six figures are produced — every mode × method:
`figures/paper_figure_A3_<mode>_<method>.png`. Edit `RENDER_MODES` / `METHODS`
at the top of `paper_figure_A3.py` to render a subset. The colour scale is
auto-fit (2–98th percentile) per mode, since S11-only Z is far more negative
than the full-array max.

## Pipeline

```
1. detectable_difference_hunter.py   Hunter CSVs -> results/detectable_diff_A3_*.npz (rows_MAX)
2. build_accuracy_csv.py             CNN/MLP LOSO json -> accuracy_data/per_position_accuracy_A3_*__{cnn,mlp}.csv
3. paper_figure_A3.py                -> figures/paper_figure_A3_{cnn,mlp}.png
```

Everything joins on the `RnCmPp` position label, so the CNN and MLP loaders'
differing (x,y) conventions don't matter.

## Data sources

| config | DD color (Hunter sessions) | dot size (LOSO accuracy) |
|---|---|---|
| A3_Empty | **1812** single session (today's antenna naming) | June18 3-session LOSO |
| A3_F4 | July03/A3_F4_SamMed (4 sessions; partial `1703` dropped) | all-4 LOSO |
| A3_F5 | July03/A3_F5_SamMed (5 sessions) | all-5 LOSO |

**Why 1812 for empty DD + the antenna remap:** June18 (empty LOSO) used a
different antenna numbering than today's F4/F5/1812 data:
- June18: 1=TL, 2=BL, 3=BR, 4=TR
- today:  1=BL, 2=TL, 3=TR, 4=BR

The empty DD *color* comes from the 1812 session (today's convention). For the
empty *accuracy*, the June18 LOSO is re-run with a **port remap** `[2,1,4,3]`
(new port a ← old port list[a-1], a swap {1↔2, 3↔4}) so its antenna numbering
matches today's — otherwise `single1`/`pair13` would size dots by the wrong
physical antenna. Those remapped runs carry the session-set label `remap`
(`build_accuracy_csv.py` points A3_Empty at them). The original June18 LOSO is
left untouched for the CNN-vs-MLP comparison.

Remap is applied in both pipelines: MLP `--port-remap 2,1,4,3`, CNN env
`CNN_LOSO_PORT_REMAP="2 1 4 3"`.

MAX-overlay median Z: −40 dB (empty) → −46 (F4) → −64 (F5) — the growing
glandular insert masks the marble. Color scale `LIM = (-90, -30)`.

## Phantom outlines (needs tracing — isolated A3 calibration)

The A3 calibration lives in `calibration/` here (a copy of the shared tools, so
it does NOT touch the A2 paper's `../calibration/calibration.json`). Photos
`A3.jpg / A3F4.jpg / A3F5.jpg` are already in `calibration/phantom_photos/`.

1. `cd calibration && python click_calibration.py`
   - **A3.jpg**: drag the 9 grid markers onto the grid intersections, then click
     points around the **adipose bowl** edge.
   - **A3F4.jpg / A3F5.jpg**: grid markers, then click points around the
     **glandular insert** edge.
2. `python apply_calibration.py` — prints `BOWL_ELLIPSE_CENTER/RX/RY`,
   `F4_OUTLINE`, `F5_OUTLINE`.
3. Paste into the "A3 OUTLINE CONSTANTS" block of `paper_figure_A3.py`:
   `F4_OUTLINE → A3_F4_OUTLINE`, `F5_OUTLINE → A3_F5_OUTLINE`, bowl constants as-is.
4. `python paper_figure_A3.py` to re-render with outlines.

## Adjusting antenna positions

The 4 antennas are in the same spot for every setup, so one shared layout drives
all three panels. To place them on the real photo:

```
cd calibration && python adjust_antennas_A3.py
```

Drag the numbered boxes (1,2,3,4) onto the antennas in `A3.jpg`. Keys: `s` save,
`u` undo, `r` reset to defaults, `z` 2× zoom; closing the window also saves. It
writes `antenna_positions_A3.json` (in `A3_hunter/`), which `paper_figure_A3.py`
loads automatically (falling back to the built-in Medium-Separated defaults).

### Antenna modes drive everything

There is no separate visibility toggle — the `MODES` / `RENDER_MODES` at the top
of `paper_figure_A3.py` control it. Each mode restricts the DD color, the
accuracy CSV, and the antenna markers to the same ports (table above), so an
`single1` figure is a true S11-only plot (S11 color + S11 accuracy + antenna 1),
and `pair13` uses only the ports-1&3 S-parameters. The panel framing stays fixed
across modes so the figures line up.

## Nudging dot positions (optional)

If inserting the glandular shifted where the marble actually sat versus its
default grid corner, use the drag tool:

```
cd calibration && python adjust_positions.py
```

For each photo (A3 / A3F4 / A3F5) it draws one marker per measured position at
its default coord; drag any that are off onto the true spot. Keys: `n` save &
next, `u` undo, `r` reset marker under cursor, `z` 2× zoom. It writes
`position_adjustments.json` (in `A3_hunter/`), which `paper_figure_A3.py` reads
automatically on the next render — only the dots you moved change.
