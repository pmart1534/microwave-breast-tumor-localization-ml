# Microwave Breast Tumor Localization with a Four-Antenna Array and Machine Learning

Code and data for the paper:

> **Machine-Learning-Based Microwave Breast Tumor Localization: Minimizing Hardware and Bandwidth**
> Peter Martin, Mouad Addad, Sam Makin, Reed Sussman, Breanna Lu, Cynthia M. Furse
> *IEEE Journal of Electromagnetics, RF, and Microwaves in Medicine and Biology*, 2026 (revised submission).

A four-antenna microwave imaging system measures all 16 complex S-parameters of a
3D-printed breast phantom (0.1-8 GHz, 791 points) and a CNN classifies the
measurement directly to a discrete tumor grid position. The pipeline uses a
single preprocessing step: complex-domain subtraction of a start-of-session
baseline (the mean of 16 no-tumor sweeps). The CNN then receives the raw 32x791
magnitude-and-phase matrix directly; no per-session statistics of any kind are
used, so each individual sweep can be classified as it is measured. The paper
evaluates the system with strict leave-one-session-out (LOSO) cross-validation
across drift-test scenarios (recalibration, antenna reattachment, antenna swap,
liquid replacement, cross-day, and a no-tumor null control), and characterizes
it through sensor-count, frequency-band, signal-component, and preprocessing
ablations plus a comparison against five classical classifiers.

Headline results (LOSO, reference scenario, 20 training epochs): 100% per-position
accuracy on the adipose-only phantom (99.3% with two antennas, 80.3% with a
single reflection coefficient), 91.9% with the medium glandular insert, 66.7%
with the largest; 95.9-100% under every setup perturbation; 2.04% (exactly
49-way chance) on the no-tumor null control.

## Repository Layout

```
matlab/
  cnn_training_v2/                Main programs behind the paper's CNN results
    Imager_CNN_LOSO.m             LOSO classification (Tables II-VII; headless via env vars)
    Imager_CNN_RegLOPO.m          Leave-one-position-out regression (Section III-F)
    Imager_CNN_XDay.m             Cross-day train->test evaluation
  cnn_training/                   Legacy two-stage hierarchical classifier (original submission)
  data_recording/                 VNA acquisition scripts

python_baselines/                 Classical-classifier comparison (Table V)
  run_baselines_loso.py           SVM / RF / LR / k-NN / MLP under the CNN-matched pipeline
  sweep_paper_baseonly_raw.py     Driver for the paper's Table V cells (raw input, baseline-only)
  run_mlp_loso.py                 Shared loading + feature pipeline
  hunter_loader.py, data.py       Dependencies (physics_features*.py retained for imports only;
                                  the paper uses --input raw)
  sweep_*.py                      Other sweep drivers

detectable_change/
  A3_hunter/                      Confidence-interval detectable-change maps (Fig. 5)
  (top level)                     Legacy A2 detectable-change analysis (original submission)

figures_paper/                    Figure build scripts (Fig. 3 antenna response, Fig. 6 loss curves)

results_paper/                    Result JSONs behind every number in Tables II-VII,
                                  the LOPO regression results, and the training curves

datasets/                         Legacy A2 two-antenna .mat data (original submission)
DATASET.md                        Layout + session manifest for the A3 dataset on IEEE DataPort
```

## Data

The revised paper's raw dataset (~11 GB of four-port VNA CSV sweeps across ten
test scenarios) is hosted on **IEEE DataPort**
(DOI: [10.21227/mcgf-0q16](https://dx.doi.org/10.21227/mcgf-0q16)). See
`DATASET.md` for the file format and the session-by-scenario manifest.

## Reproducing the paper's results

1. Download the dataset from IEEE DataPort and note the path to the
   `Separated/Aug18` folder.
2. **CNN (Tables II-IV, VI, VII):** run `matlab/cnn_training_v2/Imager_CNN_LOSO.m`.
   Headless configuration is via environment variables
   (`CNN_LOSO_PARENT`, `CNN_LOSO_EPOCHS=20`, `CNN_LOSO_INPUT=raw`,
   `CNN_LOSO_ANT_MODE`, `CNN_LOSO_PORTS`, `CNN_LOSO_BAND`, `CNN_LOSO_COMPONENT`,
   plus ablation switches documented in the script header). The paper's pipeline
   sets `CNN_LOSO_NO_MEANSUB=1`, `CNN_LOSO_ZSCORE=off`, and
   `CNN_LOSO_INPUTNORM=none` so that baseline subtraction is the only
   preprocessing (result files carry the `paperBO` tag).
3. **Classical baselines (Table V):** from `python_baselines/`,
   `python run_baselines_loso.py --setup <session parent> --antenna all|pair:1,3|single:1 --input raw --no-session-mean --no-zscore --no-input-norm --classifiers svm,rf,lr,knn,mlp`
   (or run the paper's driver, `sweep_paper_baseonly_raw.py`).
4. **Detectable-change maps (Fig. 5):** `detectable_change/A3_hunter/`
   (`detectable_difference_hunter.py` then `paper_figure_A3.py`).
5. **Unseen-position regression (Section III-F):**
   `matlab/cnn_training_v2/Imager_CNN_RegLOPO.m` (default `LOPO_MODE=pooled`).

Pre-computed outputs for every table are in `results_paper/` so the numbers can
be verified without re-running.

## Requirements

- MATLAB R2025b with Deep Learning Toolbox (GPU optional but recommended)
- Python 3.11+ with numpy, scipy, pandas, scikit-learn, matplotlib

## License

See `LICENSE`.
