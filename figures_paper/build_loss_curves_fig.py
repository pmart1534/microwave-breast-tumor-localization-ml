"""Loss-vs-epoch figure for the paper (R1.3) - 20-epoch reference-scenario
LOSO folds, re-plotted from the saved MATLAB curves with clean panel titles.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.io import loadmat
from pathlib import Path

N_EPOCHS = 20
IMG_DIR = Path(r"C:\Users\peter\Desktop\EM Imaging\Research Paper\Major Revision Round 1\Images")
RES_DIR = Path(r"C:\Users\peter\Desktop\EM Imaging\CNN vs MLP\results")

JOBS = [
    (RES_DIR / "cnn_loso_cnn_empty_paperBO_ref_curves-nomean-zsoff-innone_raw_all_ant1-2-3-4_curves.mat",
     IMG_DIR / "FigX_loss_curves_e20.png"),
    (RES_DIR / "cnn_loso_A3_MetalTumor_SwapAntLocation_swap4e20_raw_all_ant1-2-3-4_curves.mat",
     IMG_DIR / "FigX_loss_curves_swap_e20.png"),
]

def plot_row(fig, gs_row, mat_path, row_label, with_legend):
    m = loadmat(mat_path, squeeze_me=True, struct_as_record=False)
    folds = m["curveInfos"]
    n = len(folds)
    sub = gs_row.subgridspec(1, n, wspace=0.10)
    axes = []
    for i, fold in enumerate(folds, 1):
        ax = fig.add_subplot(sub[0, i - 1])
        tr = np.asarray(fold.TrainingLoss, dtype=float)
        va = np.asarray(fold.ValidationLoss, dtype=float)
        n_iter = len(tr)
        x = np.arange(1, n_iter + 1) / (n_iter / N_EPOCHS)

        ax.plot(x, tr, color="#0072B2", linewidth=0.8, label="training loss")
        va_mask = ~np.isnan(va)
        ax.plot(x[va_mask], va[va_mask], color="#D55E00", linewidth=1.3,
                marker="o", markersize=3.0,
                label="held-out session loss (monitoring only)")

        ax.set_title(f"fold {i}", fontsize=9)
        ax.set_xlabel("epoch", fontsize=9)
        ax.set_xlim(0, N_EPOCHS)
        ax.set_ylim(0, 4.7)
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.tick_params(labelsize=8)
        if i > 1:
            ax.set_yticklabels([])
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        axes.append(ax)
    axes[0].set_ylabel(f"{row_label}\ncross-entropy loss", fontsize=9)
    return axes


# Combined 2-row figure: (a) reference on top, (b) antenna swap below.
fig = plt.figure(figsize=(7.2, 5.4), dpi=200)
gs = fig.add_gridspec(2, 1, hspace=0.45, top=0.90)
ax_ref = plot_row(fig, gs[0],
         RES_DIR / "cnn_loso_cnn_empty_paperBO_ref_curves-nomean-zsoff-innone_raw_all_ant1-2-3-4_curves.mat",
         "(a) reference", with_legend=False)
plot_row(fig, gs[1],
         RES_DIR / "cnn_loso_A3_MetalTumor_SwapAntLocation_swap4e20_raw_all_ant1-2-3-4_curves.mat",
         "(b) antenna swap", with_legend=False)
handles, labels = ax_ref[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False,
           fontsize=9, bbox_to_anchor=(0.5, 0.99))
OUT = IMG_DIR / "FigX_loss_curves_ref_and_swap_e20.png"
fig.savefig(OUT, facecolor="white", bbox_inches="tight")
plt.close(fig)
print(f"wrote {OUT}")

# ---------------------------------------------------------------------------
# Single-fold version: fold 1 of the reference scenario only, sized for one
# column with larger text (the three folds are nearly identical).
m = loadmat(RES_DIR / "cnn_loso_cnn_empty_paperBO_ref_curves-nomean-zsoff-innone_raw_all_ant1-2-3-4_curves.mat",
            squeeze_me=True, struct_as_record=False)
fold = m["curveInfos"][0]
tr = np.asarray(fold.TrainingLoss, dtype=float)
va = np.asarray(fold.ValidationLoss, dtype=float)
x = np.arange(1, len(tr) + 1) / (len(tr) / N_EPOCHS)

fig, ax = plt.subplots(figsize=(4.0, 3.0), dpi=200)
ax.plot(x, tr, color="#0072B2", linewidth=1.0, label="training loss")
va_mask = ~np.isnan(va)
ax.plot(x[va_mask], va[va_mask], color="#D55E00", linewidth=1.8,
        marker="o", markersize=4.5,
        label="held-out session loss\n(monitoring only)")
ax.set_xlabel("epoch", fontsize=12)
ax.set_ylabel("cross-entropy loss", fontsize=12)
ax.set_xlim(0, N_EPOCHS)
ax.set_ylim(0, 4.7)
ax.grid(True, linestyle=":", alpha=0.5)
ax.tick_params(labelsize=11)
ax.legend(loc="upper right", frameon=False, fontsize=10)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
OUT1 = IMG_DIR / "FigX_loss_curve_single_e20.png"
fig.savefig(OUT1, facecolor="white")
plt.close(fig)
print(f"wrote {OUT1}")
