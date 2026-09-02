# Dataset: A3 Four-Antenna Microwave Breast Phantom Measurements

The raw measurement data for the revised paper (~11 GB of VNA CSV sweeps) is
hosted on **IEEE DataPort** (DOI: [10.21227/mcgf-0q16](https://dx.doi.org/10.21227/mcgf-0q16)). It is too large
for this repository; this file documents its layout and lists exactly which
session folders belong to the published dataset.

## Format

Each **session** is one folder of CSV files:

- `baseline_T01.csv` ... `baseline_T16.csv` — 16 no-tumor baseline sweeps
  recorded at the start of the session.
- `RnCmPp_T01.csv` ... `RnCmPp_T16.csv` — 16 sweeps at grid position
  row *n*, column *m*, sub-position *p*, with the tumor surrogate present.

Each CSV holds 791 frequency points (0.1-8 GHz) with columns
`Frequency, S1-1, P1-1, S2-1, P2-1, ...` giving linear magnitude (`S i-j`) and
phase in degrees (`P i-j`) for all 16 S-parameters of the four-antenna array.

Grid: 49 measurable positions on A3_Empty (0.75 in pitch); 37 on A3+F4 and
35 on A3+F5 (positions blocked by the glandular insert are skipped).

## Sessions by test scenario (paper Section II-G)

All parent paths are relative to
`DataMeasurements/Sam Antennas/MediumAntenna/Separated/Aug18/`.

| Scenario | Sessions |
|---|---|
| 1. Reference (no drift) | `A3_SamMed_MetalTumor_Session0101_20260818_1143`, `..._Session0102_20260818_1210`, `..._Session0103_20260818_1239` |
| 2. Cross-day | the three `*_2026081?_09xx/10xx` next-day metal sessions |
| 3. Fresh VNA calibration | the three fresh-calibration sessions (1103 / 1200 / 1258) |
| 4. Antenna reattachment | the reattachment sessions (1509 / 1631 / 1703 + shared 1258) |
| 5. Antenna unit swap | `A3_MetalTumor_SwapAntLocation/` (4 sessions, 0856 / 0922 / 0954 / 1020) |
| 6. Canola-oil replacement | `OilChangeandA3F4/A3_MetalTumor_OilChange01..03` (1120 / 1154 / 1225) |
| 7. Beet dielectric surrogate | the three beet sessions (1334 / 1444 / 1512) |
| 8. A3+F4 glandular | `OilChangeandA3F4/A3F4_MetalTumor_Session01..03` (1655 / 1804 / 1820) |
| 9. A3+F5 glandular | `A3F5/A3F5_MetalTumor_Session01_20260821_1317`, `..._Session02_..._1341`, `A3F5_SamMed_Metal_Session03_..._1409` |
| 10. Null control (no tumor) | the three null-control sessions (1744 / 1807 / 0802) |

The legacy two-antenna A2 dataset from the originally submitted version of the
paper remains in `datasets/` (5 small `.mat` files) for the record.
