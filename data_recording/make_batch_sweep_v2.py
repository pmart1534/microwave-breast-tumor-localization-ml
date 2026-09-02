#!/usr/bin/env python3
"""
make_batch_sweep_v2.py - Produce batch_sweep.c with PERSISTENT saved configs.

Same patching approach as v1 (patches Keysight's sweep.c → batch_sweep.c),
but the session setup block now:

  - Loads saved antennas/objects/phantoms/custom models from disk
  - Shows menus with saved items
  - Lets user add new items (and optionally save them)
  - Loads saved grid config per model
  - Loads saved skip list per model
  - After measurements, offers to save new skip positions

Persistent state lives in ./batch_configs/ next to the executable:
    antennas.list        - one antenna name per line
    objects.list         - one object name per line
    phantoms.list        - one Breast Phantom version per line (e.g. A2, F3)
    custom_models.list   - one custom (non-builtin) model name per line
    model_<name>.conf    - grid config for a specific model
    skips_<name>.list    - skip positions for a specific model

Built-in (not persisted, always shown):
    Antennas:  Medium Hoof Antenna, McGill Antenna
    Models:    ButterBox, Breast Phantom (with sub-versions)
    Objects:   (none — user adds as they go)

USAGE on the Linux machine:
    cp make_batch_sweep_v2.py ~/Internal_V2.5.7.0_x86/application/
    cd ~/Internal_V2.5.7.0_x86/application/
    python3 make_batch_sweep_v2.py
    # produces (or overwrites) batch_sweep.c
    # then add the gcc line to compile.sh (see README) and ./compile.sh
"""
import os, sys, re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SWEEP_C = SCRIPT_DIR / "sweep.c"
OUT_C   = SCRIPT_DIR / "batch_sweep.c"


# ============================================================================
# BLOCK_FWD - forward declarations of helpers, placed before int main()
# ============================================================================
BLOCK_FWD = r"""
// --- Forward declarations for batch_sweep helpers (definitions at end) ---
#define BS_MAX_SAVED 64
#define BS_NAME_LEN  128
#define BS_MAX_SKIPS 256
#define BS_LABEL_LEN 24
#define BS_CONFIG_DIR "./batch_configs"

void bs_read_line(const char *prompt, char *out, size_t outSize);
int  bs_read_int(const char *prompt, int defaultVal);
double bs_read_double(const char *prompt, double defaultVal);
int  bs_read_int_list(const char *prompt, int *out, int maxCount);
void bs_sanitize(const char *in, char *out, size_t outSize);
void bs_ensure_dir(const char *path);
void bs_grid_to_physical(int row, int col, int subPos,
                         double cellSize, double dividerThick,
                         double *xInch, double *yInch);
void bs_write_metadata(const char *path, const char *modelName,
                       const char *antennaName, const char *objectName,
                       const char *operatorName, int gridRows, int gridCols,
                       int *measureRows, int numMeasureRows,
                       int *measureCols, int numMeasureCols,
                       double cellSizeInch, double dividerInch,
                       int trialCount, int numPositions, int autoMode);
void bs_run_one_sweep(int numOfDevices, char swpTypeInput, char *unitNumber,
                      int *socketsArranged, double *startF, double *stopF,
                      double *stepF, IFBandwidth ifBw, int resultFormat,
                      int swpCnt, SweepMode mode, int delayBtwSwp,
                      int saveMode, int segSwp, int *segPort_arg,
                      bool avgSwpData, int *fd1, int *fd2,
                      pthread_t *abortThrId);
void bs_write_csv(const char *csvPath, int numOfDevices, int numPoints,
                  int swpCnt, int resultFormat, int segSwp, bool avgSwpData);

// Persistent config helpers
int  bs_load_list(const char *filename, char items[][BS_NAME_LEN], int maxItems);
void bs_save_list(const char *filename, char items[][BS_NAME_LEN], int count);
int  bs_append_unique(const char *filename, const char *item);
int  bs_load_grid_config(const char *modelName, int *gr, int *gc,
                         int *measureRows, int *nMR, int *measureCols, int *nMC,
                         double *cellSize, double *divider);
void bs_save_grid_config(const char *modelName, int gr, int gc,
                         int *measureRows, int nMR, int *measureCols, int nMC,
                         double cellSize, double divider);
int  bs_load_skip_list(const char *modelName, char skips[][BS_LABEL_LEN], int maxSkips);
void bs_save_skip_list(const char *modelName, char skips[][BS_LABEL_LEN], int count);
void bs_merge_and_save_skips(const char *modelName,
                             char existingSkips[][BS_LABEL_LEN], int nExisting,
                             char newSkips[][BS_LABEL_LEN], int nNew);
int  bs_is_in_skip_list(const char *label, char skips[][BS_LABEL_LEN], int n);
int  bs_menu_pick(const char *category,
                  const char **builtins, int nBuiltins,
                  char saved[][BS_NAME_LEN], int nSaved,
                  char *result, size_t resultSize, int *wasNew);

"""


# ============================================================================
# BLOCK_A - session setup block, placed right after "Standard Sweep Program"
# This is the BIG change: it does menu-driven selection with persistence.
# ============================================================================
BLOCK_A = r"""
  // =============================================================
  // BATCH SWEEP v2 session setup (persistent configs)
  // =============================================================
  char bs_modelName[BS_NAME_LEN]    = {0};
  char bs_antennaName[BS_NAME_LEN]  = {0};
  char bs_objectName[BS_NAME_LEN]   = {0};
  char bs_operatorName[BS_NAME_LEN] = {0};
  int  bs_gridRows = 6, bs_gridCols = 6;
  int  bs_measureRows[64], bs_numMeasureRows = 0;
  int  bs_measureCols[64], bs_numMeasureCols = 0;
  double bs_cellSizeInch = 1.0;
  double bs_dividerInch  = 0.25;
  int  bs_trialCount = 16;
  int  bs_autoMode = 0;
  double bs_autoDelaySec = 0.2;
  char bs_sessionFolder[512] = {0};

  // Skip-tracking state for the position loop
  char bs_autoSkipList[BS_MAX_SKIPS][BS_LABEL_LEN];
  int  bs_numAutoSkips = 0;
  int  bs_useAutoSkip = 0;
  char bs_sessionSkips[BS_MAX_SKIPS][BS_LABEL_LEN];
  int  bs_numSessionSkips = 0;

  // Saved lists (loaded from disk)
  char bs_savedAntennas[BS_MAX_SAVED][BS_NAME_LEN];
  char bs_savedObjects[BS_MAX_SAVED][BS_NAME_LEN];
  char bs_savedPhantoms[BS_MAX_SAVED][BS_NAME_LEN];
  char bs_savedCustomModels[BS_MAX_SAVED][BS_NAME_LEN];

  bs_ensure_dir(BS_CONFIG_DIR);
  int bs_nA = bs_load_list("antennas.list",      bs_savedAntennas,     BS_MAX_SAVED);
  int bs_nO = bs_load_list("objects.list",       bs_savedObjects,      BS_MAX_SAVED);
  int bs_nP = bs_load_list("phantoms.list",      bs_savedPhantoms,     BS_MAX_SAVED);
  int bs_nM = bs_load_list("custom_models.list", bs_savedCustomModels, BS_MAX_SAVED);

  printf("=================================================\n");
  printf("   BATCH SWEEP - Imager Data Recording (v2)\n");
  printf("=================================================\n");
  printf("Saved: %d antennas, %d objects, %d phantom versions, %d custom models\n\n",
         bs_nA, bs_nO, bs_nP, bs_nM);

  // ----- Antenna selection -----
  const char *bs_builtinAntennas[] = {"Medium Hoof Antenna", "McGill Antenna"};
  int bs_wasNew = 0;
  bs_menu_pick("Antenna", bs_builtinAntennas, 2,
               bs_savedAntennas, bs_nA,
               bs_antennaName, sizeof(bs_antennaName), &bs_wasNew);
  if (bs_wasNew) {
    char saveResp[16];
    bs_read_line("Save this antenna for future use? [y/N]: ", saveResp, sizeof(saveResp));
    if (saveResp[0] == 'y' || saveResp[0] == 'Y') {
      if (bs_append_unique("antennas.list", bs_antennaName))
        printf("  Antenna saved.\n");
    }
  }

  // ----- Object selection (no built-ins) -----
  bs_menu_pick("Object", NULL, 0,
               bs_savedObjects, bs_nO,
               bs_objectName, sizeof(bs_objectName), &bs_wasNew);
  if (bs_wasNew) {
    char saveResp[16];
    bs_read_line("Save this object for future use? [y/N]: ", saveResp, sizeof(saveResp));
    if (saveResp[0] == 'y' || saveResp[0] == 'Y') {
      if (bs_append_unique("objects.list", bs_objectName))
        printf("  Object saved.\n");
    }
  }

  // ----- Model selection (with sub-menu for Breast Phantom) -----
  const char *bs_builtinTopModels[] = {"ButterBox", "Breast Phantom"};
  char bs_topModel[BS_NAME_LEN] = {0};
  bs_menu_pick("Model", bs_builtinTopModels, 2,
               bs_savedCustomModels, bs_nM,
               bs_topModel, sizeof(bs_topModel), &bs_wasNew);

  if (strcmp(bs_topModel, "Breast Phantom") == 0) {
    // Sub-menu for phantom version
    char bs_phantomVer[BS_NAME_LEN] = {0};
    int bs_phantomNew = 0;
    bs_menu_pick("Breast Phantom version",
                 NULL, 0,
                 bs_savedPhantoms, bs_nP,
                 bs_phantomVer, sizeof(bs_phantomVer), &bs_phantomNew);
    if (bs_phantomNew) {
      char saveResp[16];
      bs_read_line("Save this phantom version for future use? [y/N]: ", saveResp, sizeof(saveResp));
      if (saveResp[0] == 'y' || saveResp[0] == 'Y') {
        if (bs_append_unique("phantoms.list", bs_phantomVer))
          printf("  Phantom version saved.\n");
      }
    }
    snprintf(bs_modelName, sizeof(bs_modelName), "BreastPhantom_%s", bs_phantomVer);
  } else {
    strncpy(bs_modelName, bs_topModel, sizeof(bs_modelName) - 1);
    if (bs_wasNew) {
      char saveResp[16];
      bs_read_line("Save this model for future use? [y/N]: ", saveResp, sizeof(saveResp));
      if (saveResp[0] == 'y' || saveResp[0] == 'Y') {
        if (bs_append_unique("custom_models.list", bs_modelName))
          printf("  Model saved.\n");
      }
    }
  }
  printf("\nModel: %s\n\n", bs_modelName);

  // ----- Grid config (load saved or prompt new) -----
  int bs_haveSavedGrid = bs_load_grid_config(bs_modelName,
                                              &bs_gridRows, &bs_gridCols,
                                              bs_measureRows, &bs_numMeasureRows,
                                              bs_measureCols, &bs_numMeasureCols,
                                              &bs_cellSizeInch, &bs_dividerInch);
  int bs_useSavedGrid = 0;
  if (bs_haveSavedGrid) {
    printf("Saved grid for model '%s':\n", bs_modelName);
    printf("  Grid: %dx%d\n", bs_gridRows, bs_gridCols);
    printf("  Measured rows:");
    for (int ii = 0; ii < bs_numMeasureRows; ii++) printf(" %d", bs_measureRows[ii]);
    printf("\n  Measured cols:");
    for (int ii = 0; ii < bs_numMeasureCols; ii++) printf(" %d", bs_measureCols[ii]);
    printf("\n  Cell size: %.3f in,  Divider: %.3f in\n", bs_cellSizeInch, bs_dividerInch);
    char useResp[16];
    bs_read_line("Use these saved grid settings? [Y/n]: ", useResp, sizeof(useResp));
    bs_useSavedGrid = !(useResp[0] == 'n' || useResp[0] == 'N');
  } else if (strcmp(bs_modelName, "ButterBox") == 0) {
    // ButterBox built-in defaults: 6x6 grid, inner 4x4 measured
    printf("ButterBox default grid: 6x6, measuring rows 2-5 cols 2-5, 1.0\" cells, 0.25\" dividers.\n");
    char useResp[16];
    bs_read_line("Use these ButterBox defaults? [Y/n]: ", useResp, sizeof(useResp));
    if (!(useResp[0] == 'n' || useResp[0] == 'N')) {
      bs_gridRows = 6; bs_gridCols = 6;
      bs_numMeasureRows = 4; bs_numMeasureCols = 4;
      for (int i = 0; i < 4; i++) { bs_measureRows[i] = i + 2; bs_measureCols[i] = i + 2; }
      bs_cellSizeInch = 1.0; bs_dividerInch = 0.25;
      bs_useSavedGrid = 1;
    }
  }

  if (!bs_useSavedGrid) {
    bs_gridRows      = bs_read_int   ("Total grid rows: ", 6);
    bs_gridCols      = bs_read_int   ("Total grid columns: ", 6);
    bs_numMeasureRows = bs_read_int_list("Row numbers to MEASURE (space-separated): ",
                                         bs_measureRows, 64);
    bs_numMeasureCols = bs_read_int_list("Column numbers to MEASURE (space-separated): ",
                                         bs_measureCols, 64);
    bs_cellSizeInch  = bs_read_double("Cell size in inches [1.0]: ", 1.0);
    bs_dividerInch   = bs_read_double("Divider thickness in inches [0.25]: ", 0.25);

    char saveResp[16];
    bs_read_line("Save this grid config for this model? [Y/n]: ", saveResp, sizeof(saveResp));
    if (!(saveResp[0] == 'n' || saveResp[0] == 'N')) {
      bs_save_grid_config(bs_modelName, bs_gridRows, bs_gridCols,
                          bs_measureRows, bs_numMeasureRows,
                          bs_measureCols, bs_numMeasureCols,
                          bs_cellSizeInch, bs_dividerInch);
      printf("  Grid config saved for '%s'.\n", bs_modelName);
    }
  }

  // ----- Skip list (load if exists, ask if auto-skip) -----
  bs_numAutoSkips = bs_load_skip_list(bs_modelName, bs_autoSkipList, BS_MAX_SKIPS);
  if (bs_numAutoSkips > 0) {
    printf("\nSaved skip list for '%s' (%d positions):\n", bs_modelName, bs_numAutoSkips);
    for (int ii = 0; ii < bs_numAutoSkips; ii++) printf("  %s\n", bs_autoSkipList[ii]);
    char useResp[16];
    bs_read_line("Auto-skip these positions this session? [Y/n]: ", useResp, sizeof(useResp));
    bs_useAutoSkip = !(useResp[0] == 'n' || useResp[0] == 'N');
  }

  // ----- Operator and trial count -----
  bs_read_line("\nOperator name: ", bs_operatorName, sizeof(bs_operatorName));
  bs_trialCount = bs_read_int("Trials per position [16]: ", 16);

  // ----- Recording mode -----
  {
    char modeBuf[16] = {0};
    bs_read_line("Recording mode - (A)utomatic or (I)nteractive [I]: ",
                 modeBuf, sizeof(modeBuf));
    if (modeBuf[0] == 'A' || modeBuf[0] == 'a') {
      bs_autoMode = 1;
      bs_autoDelaySec = bs_read_double("Delay between auto sweeps in seconds [0.2]: ", 0.2);
    } else {
      bs_autoMode = 0;
    }
  }

  int bs_numPositions = bs_numMeasureRows * bs_numMeasureCols * 4;

  // ----- Build session folder -----
  {
    time_t bs_now = time(NULL);
    struct tm bs_tm = *localtime(&bs_now);
    char bs_modelClean[BS_NAME_LEN], bs_objectClean[BS_NAME_LEN];
    bs_sanitize(bs_modelName,  bs_modelClean,  sizeof(bs_modelClean));
    bs_sanitize(bs_objectName, bs_objectClean, sizeof(bs_objectClean));
    snprintf(bs_sessionFolder, sizeof(bs_sessionFolder),
             "./Data/%s_%s_%04d%02d%02d_%02d%02d",
             bs_modelClean, bs_objectClean,
             bs_tm.tm_year + 1900, bs_tm.tm_mon + 1, bs_tm.tm_mday,
             bs_tm.tm_hour, bs_tm.tm_min);
    bs_ensure_dir("./Data");
    bs_ensure_dir(bs_sessionFolder);
  }

  printf("\n-------------------------------------------------\n");
  printf("Session folder: %s\n", bs_sessionFolder);
  printf("Positions: %d   Trials/pos: %d   Total sweeps: %d\n",
         bs_numPositions, bs_trialCount, bs_numPositions * bs_trialCount);
  printf("Mode: %s   Auto-skip: %s\n",
         bs_autoMode ? "AUTOMATIC" : "INTERACTIVE",
         bs_useAutoSkip ? "yes" : "no");
  printf("-------------------------------------------------\n");
  printf("After Keysight setup completes you'll be prompted at each position.\n");
  printf("Press Enter to continue with VNA setup...\n");
  { int c; while ((c = getchar()) != '\n' && c != EOF) {} }

  // Write session metadata up front
  {
    char bs_metaPath[640];
    snprintf(bs_metaPath, sizeof(bs_metaPath), "%s/session_metadata.txt", bs_sessionFolder);
    bs_write_metadata(bs_metaPath, bs_modelName, bs_antennaName, bs_objectName,
                      bs_operatorName, bs_gridRows, bs_gridCols,
                      bs_measureRows, bs_numMeasureRows,
                      bs_measureCols, bs_numMeasureCols,
                      bs_cellSizeInch, bs_dividerInch,
                      bs_trialCount, bs_numPositions, bs_autoMode);
  }
  // =============================================================
  // end BATCH SWEEP v2 session setup
  // =============================================================

"""


# ============================================================================
# BLOCK_B - position×trial loop (with skip tracking and end-of-session save)
# Replaces the entire while(1) repeat block from sweep.c.
# ============================================================================
BLOCK_B = r"""
  // =============================================================
  // BATCH SWEEP v2 - position x trial loop with skip tracking
  // =============================================================
  {
    char bs_csvPath[640];
    const char *bs_subNames[4] = {"Top-Left", "Top-Right", "Bottom-Right", "Bottom-Left"};

    // ---------- Baseline sweeps ----------
    printf("\n=================================================\n");
    printf("   BASELINE - remove all objects from container\n");
    printf("=================================================\n");
    printf("Press Enter when ready for %d baseline sweep(s)...\n", bs_trialCount);
    { int c; while ((c = getchar()) != '\n' && c != EOF) {} }

    for (int bs_t = 0; bs_t < bs_trialCount; bs_t++) {
      if (!bs_autoMode) {
        printf("  Baseline %d/%d - press Enter to sweep...", bs_t + 1, bs_trialCount);
        fflush(stdout);
        { int c; while ((c = getchar()) != '\n' && c != EOF) {} }
      } else {
        printf("  Baseline %d/%d ... ", bs_t + 1, bs_trialCount);
        fflush(stdout);
      }

      bs_run_one_sweep(numOfDevices, swpTypeInput, &unitNumber[0], socketsArranged,
                       &startF, &stopF, &stepF, ifBw, resultFormat, swpCnt, mode,
                       delayBtwSwp, saveMode, segSwp, segPort,
                       avgSwpData, &fd1, &fd2, &abortThrId);

      snprintf(bs_csvPath, sizeof(bs_csvPath), "%s/baseline_T%02d.csv",
               bs_sessionFolder, bs_t + 1);
      bs_write_csv(bs_csvPath, numOfDevices,
                   segSwp == 1 ? segNumOfFreqPoints : numOfSweepPoints,
                   swpCnt, resultFormat, segSwp, avgSwpData);
      printf("-> %s\n", bs_csvPath + strlen(bs_sessionFolder) + 1);

      if (bs_autoMode && bs_t < bs_trialCount - 1) {
        usleep((useconds_t)(bs_autoDelaySec * 1e6));
      }
    }

    // ---------- Position x trial loop ----------
    printf("\n=================================================\n");
    printf("   DATA COLLECTION  (%d positions x %d trials)\n",
           bs_numPositions, bs_trialCount);
    printf("=================================================\n");

    int bs_skipped = 0;
    int bs_pIdx = 0;
    for (int bs_ri = 0; bs_ri < bs_numMeasureRows; bs_ri++) {
      int bs_row = bs_measureRows[bs_ri];
      for (int bs_ci = 0; bs_ci < bs_numMeasureCols; bs_ci++) {
        int bs_col = bs_measureCols[bs_ci];
        for (int bs_sp = 1; bs_sp <= 4; bs_sp++) {
          bs_pIdx++;
          double bs_x, bs_y;
          bs_grid_to_physical(bs_row, bs_col, bs_sp,
                              bs_cellSizeInch, bs_dividerInch, &bs_x, &bs_y);
          char bs_label[BS_LABEL_LEN];
          snprintf(bs_label, sizeof(bs_label), "R%dC%dP%d", bs_row, bs_col, bs_sp);

          printf("\n--------------------------------------------\n");
          printf("POSITION %d/%d   R%d C%d %s (P%d)\n",
                 bs_pIdx, bs_numPositions, bs_row, bs_col,
                 bs_subNames[bs_sp - 1], bs_sp);
          printf("  Physical: (%.2f, %.2f) inches\n", bs_x, bs_y);
          printf("--------------------------------------------\n");

          // Check auto-skip list
          int bs_autoSkipped = (bs_useAutoSkip &&
                                bs_is_in_skip_list(bs_label,
                                                   bs_autoSkipList,
                                                   bs_numAutoSkips));
          char bs_resp[16] = {0};
          if (bs_autoSkipped) {
            bs_read_line("  ** AUTO-SKIPPED (saved). Type '0' to measure anyway, or Enter to confirm skip: ",
                         bs_resp, sizeof(bs_resp));
            if (bs_resp[0] != '0') {
              // Add to session-skipped list
              if (bs_numSessionSkips < BS_MAX_SKIPS) {
                strncpy(bs_sessionSkips[bs_numSessionSkips], bs_label, BS_LABEL_LEN - 1);
                bs_sessionSkips[bs_numSessionSkips][BS_LABEL_LEN - 1] = '\0';
                bs_numSessionSkips++;
              }
              bs_skipped++;
              printf("  SKIPPED %s\n", bs_label);
              continue;
            } else {
              printf("  Override: will measure this position.\n");
            }
          } else {
            while (1) {
              bs_read_line("Place object. Type '0' to confirm, 's' to skip: ",
                           bs_resp, sizeof(bs_resp));
              if (bs_resp[0] == '0') break;
              if (bs_resp[0] == 's' || bs_resp[0] == 'S') break;
              printf("  Type '0' to confirm or 's' to skip.\n");
            }
            if (bs_resp[0] == 's' || bs_resp[0] == 'S') {
              if (bs_numSessionSkips < BS_MAX_SKIPS) {
                strncpy(bs_sessionSkips[bs_numSessionSkips], bs_label, BS_LABEL_LEN - 1);
                bs_sessionSkips[bs_numSessionSkips][BS_LABEL_LEN - 1] = '\0';
                bs_numSessionSkips++;
              }
              bs_skipped++;
              printf("  SKIPPED %s.\n", bs_label);
              continue;
            }
          }

          // Measure trialCount times at this position
          for (int bs_t = 0; bs_t < bs_trialCount; bs_t++) {
            if (!bs_autoMode) {
              char bs_pr[64];
              snprintf(bs_pr, sizeof(bs_pr),
                       "  Trial %d/%d - press Enter to sweep...",
                       bs_t + 1, bs_trialCount);
              printf("%s", bs_pr);
              fflush(stdout);
              { int c; while ((c = getchar()) != '\n' && c != EOF) {} }
            } else {
              printf("  Trial %d/%d ... ", bs_t + 1, bs_trialCount);
              fflush(stdout);
            }

            bs_run_one_sweep(numOfDevices, swpTypeInput, &unitNumber[0],
                             socketsArranged, &startF, &stopF, &stepF, ifBw,
                             resultFormat, swpCnt, mode, delayBtwSwp,
                             saveMode, segSwp, segPort,
                             avgSwpData, &fd1, &fd2, &abortThrId);

            snprintf(bs_csvPath, sizeof(bs_csvPath),
                     "%s/%s_T%02d.csv", bs_sessionFolder,
                     bs_label, bs_t + 1);
            bs_write_csv(bs_csvPath, numOfDevices,
                         segSwp == 1 ? segNumOfFreqPoints : numOfSweepPoints,
                         swpCnt, resultFormat, segSwp, avgSwpData);
            printf("-> %s_T%02d.csv\n", bs_label, bs_t + 1);

            if (bs_autoMode && bs_t < bs_trialCount - 1) {
              usleep((useconds_t)(bs_autoDelaySec * 1e6));
            }
          }
        }
      }
    }

    printf("\n=================================================\n");
    printf("   DATA COLLECTION COMPLETE\n");
    printf("=================================================\n");
    printf("Session folder:    %s\n", bs_sessionFolder);
    printf("Positions taken:   %d / %d\n", bs_numPositions - bs_skipped, bs_numPositions);
    printf("Positions skipped: %d this session\n", bs_skipped);

    // ---------- Offer to save session skips ----------
    if (bs_numSessionSkips > 0) {
      printf("\nSkipped positions this session:\n");
      for (int ii = 0; ii < bs_numSessionSkips; ii++)
        printf("  %s\n", bs_sessionSkips[ii]);
      char saveResp[16];
      bs_read_line("Save these skips (merged with existing) to model's skip list? [Y/n]: ",
                   saveResp, sizeof(saveResp));
      if (!(saveResp[0] == 'n' || saveResp[0] == 'N')) {
        bs_merge_and_save_skips(bs_modelName,
                                bs_autoSkipList, bs_numAutoSkips,
                                bs_sessionSkips, bs_numSessionSkips);
        printf("  Skip list updated for '%s'.\n", bs_modelName);
      }
    }

    printf("=================================================\n\n");

    // Cleanup
    if (saveMode == SAVETOMEM || saveMode == SAVETOMEMANDFILE) {
      fd1 = shm_unlink(STORAGE_ID1);
      if (fd1 == -1) perror("unlink STORAGE_ID1");
      fd2 = shm_unlink(STORAGE_ID2);
      if (fd2 == -1) perror("unlink STORAGE_ID2");
    }
    rStatus = DisconnectEthernet(numOfDevices, socketsArranged);
    return 0;
  }
  // =============================================================
  // end BATCH SWEEP v2 position-trial loop
  // =============================================================
"""


# ============================================================================
# BLOCK_C - helper function definitions appended at end of file
# ============================================================================
BLOCK_C = r"""
// =============================================================
// BATCH SWEEP v2 helpers
// =============================================================
#include <sys/stat.h>
#include <sys/types.h>
#include <dirent.h>

void bs_read_line(const char *prompt, char *out, size_t outSize) {
  printf("%s", prompt);
  fflush(stdout);
  if (fgets(out, (int)outSize, stdin) == NULL) {
    out[0] = '\0';
    return;
  }
  size_t L = strlen(out);
  while (L > 0 && (out[L-1] == '\n' || out[L-1] == '\r')) out[--L] = '\0';
}

int bs_read_int(const char *prompt, int defaultVal) {
  char buf[64];
  bs_read_line(prompt, buf, sizeof(buf));
  if (buf[0] == '\0') return defaultVal;
  return atoi(buf);
}

double bs_read_double(const char *prompt, double defaultVal) {
  char buf[64];
  bs_read_line(prompt, buf, sizeof(buf));
  if (buf[0] == '\0') return defaultVal;
  return atof(buf);
}

int bs_read_int_list(const char *prompt, int *out, int maxCount) {
  char buf[512];
  bs_read_line(prompt, buf, sizeof(buf));
  int n = 0;
  char *tok = strtok(buf, " ,\t");
  while (tok && n < maxCount) {
    out[n++] = atoi(tok);
    tok = strtok(NULL, " ,\t");
  }
  return n;
}

void bs_sanitize(const char *in, char *out, size_t outSize) {
  size_t i = 0, j = 0;
  while (in[i] && j + 1 < outSize) {
    char c = in[i];
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
        (c >= '0' && c <= '9') || c == '_' || c == '-') {
      out[j++] = c;
    } else if (c == ' ') {
      out[j++] = '_';
    }
    i++;
  }
  out[j] = '\0';
  if (j == 0) { strncpy(out, "Unnamed", outSize - 1); out[outSize - 1] = '\0'; }
}

void bs_ensure_dir(const char *path) {
  DIR *d = opendir(path);
  if (d) { closedir(d); return; }
  if (errno == ENOENT) mkdir(path, 0777);
}

void bs_grid_to_physical(int row, int col, int subPos,
                         double cellSize, double dividerThick,
                         double *xInch, double *yInch) {
  double halfDiv = dividerThick / 2.0;
  double offset  = (cellSize / 2.0) - halfDiv;
  double dx = 0.0, dy = 0.0;
  switch (subPos) {
    case 1: dx = -offset; dy = -offset; break;
    case 2: dx = +offset; dy = -offset; break;
    case 3: dx = +offset; dy = +offset; break;
    case 4: dx = -offset; dy = +offset; break;
    default: break;
  }
  *xInch = (col - 0.5) * cellSize + dx;
  *yInch = (row - 0.5) * cellSize + dy;
}

void bs_write_metadata(const char *path, const char *modelName,
                       const char *antennaName, const char *objectName,
                       const char *operatorName, int gridRows, int gridCols,
                       int *measureRows, int numMeasureRows,
                       int *measureCols, int numMeasureCols,
                       double cellSizeInch, double dividerInch,
                       int trialCount, int numPositions, int autoMode) {
  FILE *f = fopen(path, "w");
  if (!f) return;
  time_t t = time(NULL);
  struct tm tm = *localtime(&t);
  fprintf(f, "Hunter VNA Batch Sweep - Session Metadata\n");
  fprintf(f, "==========================================\n\n");
  fprintf(f, "Timestamp:  %04d-%02d-%02d %02d:%02d:%02d\n",
          tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday,
          tm.tm_hour, tm.tm_min, tm.tm_sec);
  fprintf(f, "Operator:   %s\n", operatorName);
  fprintf(f, "Model:      %s\n", modelName);
  fprintf(f, "Antenna:    %s\n", antennaName);
  fprintf(f, "Object:     %s\n", objectName);
  fprintf(f, "\nGrid Configuration\n");
  fprintf(f, "  Total grid:    %d rows x %d cols\n", gridRows, gridCols);
  fprintf(f, "  Measured rows:");
  for (int i = 0; i < numMeasureRows; i++) fprintf(f, " %d", measureRows[i]);
  fprintf(f, "\n  Measured cols:");
  for (int i = 0; i < numMeasureCols; i++) fprintf(f, " %d", measureCols[i]);
  fprintf(f, "\n  Cell size:     %.3f inches\n", cellSizeInch);
  fprintf(f, "  Divider thick: %.3f inches\n", dividerInch);
  fprintf(f, "\nMeasurement Plan\n");
  fprintf(f, "  Positions:           %d\n", numPositions);
  fprintf(f, "  Trials per position: %d\n", trialCount);
  fprintf(f, "  Total sweeps:        %d (+ %d baseline)\n",
          numPositions * trialCount, trialCount);
  fprintf(f, "  Mode:                %s\n", autoMode ? "AUTOMATIC" : "INTERACTIVE");
  fprintf(f, "\nFile Naming\n");
  fprintf(f, "  baseline_TNN.csv       baseline trial NN\n");
  fprintf(f, "  RnCmPp_TNN.csv         row n, col m, sub-position p (1-4), trial NN\n");
  fprintf(f, "    P1=Top-Left  P2=Top-Right  P3=Bottom-Right  P4=Bottom-Left\n");
  fclose(f);
}

void bs_run_one_sweep(int numOfDevices, char swpTypeInput, char *unitNumber,
                      int *socketsArranged, double *startF, double *stopF,
                      double *stepF, IFBandwidth ifBw, int resultFormat,
                      int swpCnt, SweepMode mode, int delayBtwSwp,
                      int saveMode, int segSwp, int *segPort_arg,
                      bool avgSwpData, int *fd1, int *fd2,
                      pthread_t *abortThrId) {
  MN7021aErrType rStatus = MN7021aERR_NONE;
  int complete = 1;
  (void)avgSwpData;
  (void)segPort_arg;

  signal(SIGINT, sig_handler);
  set_conio_terminal_mode();
  pthread_create(abortThrId, NULL, AbortSweepIntrpt, NULL);

  if (segSwp == 1) {
    rStatus = EthernetInitSegmentedFrequencySweepRawData(
        numOfDevices, swpTypeInput, unitNumber, socketsArranged,
        resultFormat, swpCnt, false, saveMode, segPort);
  } else {
    rStatus = EthernetInitFrequencySweepRawData(
        numOfDevices, swpTypeInput, unitNumber, socketsArranged,
        startF, stopF, stepF, ifBw, resultFormat, swpCnt, mode,
        delayBtwSwp, false, saveMode);
  }

  signal(SIGINT, SIG_DFL);
  complete = CheckSweepComplete();
  if (complete == 0) complete = 1;
  pthread_cancel(*abortThrId);
  pthread_detach(*abortThrId);
  reset_terminal_mode();

  if (rStatus != MN7021aERR_NONE) {
    printf("[WARN] Sweep returned error %d\n", (int)rStatus);
    return;
  }

  if (saveMode == SAVETOMEM || saveMode == SAVETOMEMANDFILE) {
    if (segSwp == 1) {
      ReadResultFromMemorySegmented(STORAGE_ID1, STORAGE_ID2,
                                    SParam1shm, SParam2shm,
                                    numOfDevices, segNumOfFreqPoints, swpCnt);
    } else {
      ReadResultFromMemoryWithExistingShm(fd1, fd2,
                                          SParam1shm, SParam2shm,
                                          numOfDevices, *startF, *stopF, *stepF,
                                          swpCnt);
    }
  }
}

void bs_write_csv(const char *csvPath, int numOfDevices, int numPoints,
                  int swpCnt, int resultFormat, int segSwp, bool avgSwpData) {
  FILE *fp = fopen(csvPath, "w");
  if (!fp) {
    fprintf(stderr, "[ERROR] Cannot open %s for writing\n", csvPath);
    return;
  }
  if (segSwp == 1) {
    if (avgSwpData) {
      PrintSweepResToFileSegmented(fp, numOfDevices, numPoints, 0,
                                   resultFormat, SParam1shm, SParam2shm);
    } else {
      for (int i = 0; i < swpCnt; i++) {
        PrintSweepResToFileSegmented(fp, numOfDevices, numPoints, i,
                                     resultFormat, SParam1shm, SParam2shm);
      }
    }
  } else {
    if (avgSwpData) {
      PrintSweepResToFile(fp, numOfDevices, numPoints, 0,
                          resultFormat, SParam1shm, SParam2shm);
    } else {
      for (int i = 0; i < swpCnt; i++) {
        PrintSweepResToFile(fp, numOfDevices, numPoints, i,
                            resultFormat, SParam1shm, SParam2shm);
      }
    }
  }
  fclose(fp);
}

// ---------- Persistent config helpers ----------

int bs_load_list(const char *filename, char items[][BS_NAME_LEN], int maxItems) {
  char path[512];
  snprintf(path, sizeof(path), "%s/%s", BS_CONFIG_DIR, filename);
  FILE *f = fopen(path, "r");
  if (!f) return 0;
  int n = 0;
  char buf[BS_NAME_LEN];
  while (n < maxItems && fgets(buf, sizeof(buf), f)) {
    size_t L = strlen(buf);
    while (L > 0 && (buf[L-1] == '\n' || buf[L-1] == '\r')) buf[--L] = '\0';
    if (L == 0) continue;
    strncpy(items[n], buf, BS_NAME_LEN - 1);
    items[n][BS_NAME_LEN - 1] = '\0';
    n++;
  }
  fclose(f);
  return n;
}

void bs_save_list(const char *filename, char items[][BS_NAME_LEN], int count) {
  char path[512];
  snprintf(path, sizeof(path), "%s/%s", BS_CONFIG_DIR, filename);
  FILE *f = fopen(path, "w");
  if (!f) return;
  for (int i = 0; i < count; i++) fprintf(f, "%s\n", items[i]);
  fclose(f);
}

int bs_append_unique(const char *filename, const char *item) {
  if (item[0] == '\0') return 0;
  char items[BS_MAX_SAVED][BS_NAME_LEN];
  int n = bs_load_list(filename, items, BS_MAX_SAVED);
  for (int i = 0; i < n; i++) {
    if (strcmp(items[i], item) == 0) return 0;  // already there
  }
  if (n >= BS_MAX_SAVED) return 0;
  strncpy(items[n], item, BS_NAME_LEN - 1);
  items[n][BS_NAME_LEN - 1] = '\0';
  n++;
  bs_save_list(filename, items, n);
  return 1;
}

int bs_load_grid_config(const char *modelName, int *gr, int *gc,
                        int *measureRows, int *nMR, int *measureCols, int *nMC,
                        double *cellSize, double *divider) {
  char cleanName[BS_NAME_LEN];
  bs_sanitize(modelName, cleanName, sizeof(cleanName));
  char path[512];
  snprintf(path, sizeof(path), "%s/model_%s.conf", BS_CONFIG_DIR, cleanName);
  FILE *f = fopen(path, "r");
  if (!f) return 0;
  char buf[512];
  *nMR = 0; *nMC = 0;
  while (fgets(buf, sizeof(buf), f)) {
    if (strncmp(buf, "GridRows=", 9) == 0) *gr = atoi(buf + 9);
    else if (strncmp(buf, "GridCols=", 9) == 0) *gc = atoi(buf + 9);
    else if (strncmp(buf, "CellSize=", 9) == 0) *cellSize = atof(buf + 9);
    else if (strncmp(buf, "Divider=", 8) == 0) *divider = atof(buf + 8);
    else if (strncmp(buf, "MeasureRows=", 12) == 0) {
      char *tok = strtok(buf + 12, " \n\r\t,");
      while (tok && *nMR < 64) { measureRows[(*nMR)++] = atoi(tok); tok = strtok(NULL, " \n\r\t,"); }
    }
    else if (strncmp(buf, "MeasureCols=", 12) == 0) {
      char *tok = strtok(buf + 12, " \n\r\t,");
      while (tok && *nMC < 64) { measureCols[(*nMC)++] = atoi(tok); tok = strtok(NULL, " \n\r\t,"); }
    }
  }
  fclose(f);
  return (*nMR > 0 && *nMC > 0);
}

void bs_save_grid_config(const char *modelName, int gr, int gc,
                         int *measureRows, int nMR, int *measureCols, int nMC,
                         double cellSize, double divider) {
  char cleanName[BS_NAME_LEN];
  bs_sanitize(modelName, cleanName, sizeof(cleanName));
  char path[512];
  snprintf(path, sizeof(path), "%s/model_%s.conf", BS_CONFIG_DIR, cleanName);
  FILE *f = fopen(path, "w");
  if (!f) return;
  fprintf(f, "ModelName=%s\n", modelName);
  fprintf(f, "GridRows=%d\n", gr);
  fprintf(f, "GridCols=%d\n", gc);
  fprintf(f, "MeasureRows=");
  for (int i = 0; i < nMR; i++) fprintf(f, "%d%s", measureRows[i], (i < nMR - 1) ? " " : "");
  fprintf(f, "\nMeasureCols=");
  for (int i = 0; i < nMC; i++) fprintf(f, "%d%s", measureCols[i], (i < nMC - 1) ? " " : "");
  fprintf(f, "\nCellSize=%.6f\nDivider=%.6f\n", cellSize, divider);
  fclose(f);
}

int bs_load_skip_list(const char *modelName, char skips[][BS_LABEL_LEN], int maxSkips) {
  char cleanName[BS_NAME_LEN];
  bs_sanitize(modelName, cleanName, sizeof(cleanName));
  char path[512];
  snprintf(path, sizeof(path), "%s/skips_%s.list", BS_CONFIG_DIR, cleanName);
  FILE *f = fopen(path, "r");
  if (!f) return 0;
  int n = 0;
  char buf[BS_LABEL_LEN + 8];
  while (n < maxSkips && fgets(buf, sizeof(buf), f)) {
    size_t L = strlen(buf);
    while (L > 0 && (buf[L-1] == '\n' || buf[L-1] == '\r')) buf[--L] = '\0';
    if (L == 0) continue;
    strncpy(skips[n], buf, BS_LABEL_LEN - 1);
    skips[n][BS_LABEL_LEN - 1] = '\0';
    n++;
  }
  fclose(f);
  return n;
}

void bs_save_skip_list(const char *modelName, char skips[][BS_LABEL_LEN], int count) {
  char cleanName[BS_NAME_LEN];
  bs_sanitize(modelName, cleanName, sizeof(cleanName));
  char path[512];
  snprintf(path, sizeof(path), "%s/skips_%s.list", BS_CONFIG_DIR, cleanName);
  FILE *f = fopen(path, "w");
  if (!f) return;
  for (int i = 0; i < count; i++) fprintf(f, "%s\n", skips[i]);
  fclose(f);
}

void bs_merge_and_save_skips(const char *modelName,
                             char existingSkips[][BS_LABEL_LEN], int nExisting,
                             char newSkips[][BS_LABEL_LEN], int nNew) {
  char merged[BS_MAX_SKIPS][BS_LABEL_LEN];
  int nMerged = 0;
  // copy existing
  for (int i = 0; i < nExisting && nMerged < BS_MAX_SKIPS; i++) {
    strncpy(merged[nMerged], existingSkips[i], BS_LABEL_LEN - 1);
    merged[nMerged][BS_LABEL_LEN - 1] = '\0';
    nMerged++;
  }
  // append new ones if not already present
  for (int i = 0; i < nNew; i++) {
    int dup = 0;
    for (int j = 0; j < nMerged; j++) {
      if (strcmp(merged[j], newSkips[i]) == 0) { dup = 1; break; }
    }
    if (!dup && nMerged < BS_MAX_SKIPS) {
      strncpy(merged[nMerged], newSkips[i], BS_LABEL_LEN - 1);
      merged[nMerged][BS_LABEL_LEN - 1] = '\0';
      nMerged++;
    }
  }
  bs_save_skip_list(modelName, merged, nMerged);
}

int bs_is_in_skip_list(const char *label, char skips[][BS_LABEL_LEN], int n) {
  for (int i = 0; i < n; i++) {
    if (strcmp(skips[i], label) == 0) return 1;
  }
  return 0;
}

int bs_menu_pick(const char *category,
                 const char **builtins, int nBuiltins,
                 char saved[][BS_NAME_LEN], int nSaved,
                 char *result, size_t resultSize, int *wasNew) {
  *wasNew = 0;
  while (1) {
    printf("\n%s:\n", category);
    int idx = 1;
    for (int i = 0; i < nBuiltins; i++) printf("  [%2d] %s\n", idx++, builtins[i]);
    for (int i = 0; i < nSaved; i++)   printf("  [%2d] %s (saved)\n", idx++, saved[i]);
    int newIdx = idx;
    printf("  [%2d] (enter new)\n", newIdx);
    int total = nBuiltins + nSaved + 1;

    char buf[64];
    char prompt[128];
    snprintf(prompt, sizeof(prompt), "Select [1]: ");
    bs_read_line(prompt, buf, sizeof(buf));
    int choice = (buf[0] == '\0') ? 1 : atoi(buf);
    if (choice < 1 || choice > total) {
      printf("  Invalid choice, try again.\n");
      continue;
    }
    if (choice <= nBuiltins) {
      strncpy(result, builtins[choice - 1], resultSize - 1);
      result[resultSize - 1] = '\0';
      return 0;
    }
    if (choice <= nBuiltins + nSaved) {
      strncpy(result, saved[choice - nBuiltins - 1], resultSize - 1);
      result[resultSize - 1] = '\0';
      return 0;
    }
    // (enter new)
    char nameBuf[BS_NAME_LEN];
    bs_read_line("Enter new name: ", nameBuf, sizeof(nameBuf));
    if (nameBuf[0] == '\0') {
      printf("  Empty name, try again.\n");
      continue;
    }
    strncpy(result, nameBuf, resultSize - 1);
    result[resultSize - 1] = '\0';
    *wasNew = 1;
    return 0;
  }
}
// =============================================================
// end BATCH SWEEP v2 helpers
// =============================================================
"""


# ============================================================================
# Main script driver: read sweep.c, patch in three places, write batch_sweep.c
# ============================================================================
def main():
    if not SWEEP_C.exists():
        print(f"ERROR: {SWEEP_C} not found.")
        print("Run this script from the application/ folder (where sweep.c lives).")
        sys.exit(1)

    src = SWEEP_C.read_text()

    # Sanity check
    if "Standard Sweep Program" not in src:
        print("ERROR: sweep.c does not contain expected anchor 'Standard Sweep Program'.")
        sys.exit(1)
    if "Do you want to repeat the sweep" not in src:
        print("ERROR: sweep.c does not contain expected anchor 'Do you want to repeat the sweep'.")
        sys.exit(1)

    out = src

    # 1) Insert forward declarations before int main(void)
    anchor = "int main(void)"
    if anchor not in out:
        print(f"ERROR: cannot find '{anchor}' in sweep.c")
        sys.exit(1)
    out = out.replace(anchor, BLOCK_FWD + "\n" + anchor, 1)

    # 2) Insert BLOCK_A after the "Standard Sweep Program" printf
    anchor_a = 'printf("Standard Sweep Program\\n");'
    if anchor_a not in out:
        print(f"ERROR: cannot find anchor for BLOCK_A.")
        sys.exit(1)
    out = out.replace(anchor_a, anchor_a + "\n" + BLOCK_A, 1)

    # 3) Replace the `while(1) { ... }` repeat block with BLOCK_B
    repeat_re = re.compile(
        r"// enter into a repeat mechanism where user will determine is the sweep is to be repeated\s*"
        r"while\(1\)\s*\{",
        re.MULTILINE,
    )
    m = repeat_re.search(out)
    if not m:
        print("ERROR: cannot find the 'enter into a repeat mechanism' anchor.")
        sys.exit(1)

    start_brace = m.end() - 1
    depth = 0
    i = start_brace
    end_brace = -1
    while i < len(out):
        c = out[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end_brace = i
                break
        i += 1
    if end_brace == -1:
        print("ERROR: could not find matching '}' for while(1) block.")
        sys.exit(1)

    block_start = m.start()
    block_end = end_brace + 1
    out = out[:block_start] + BLOCK_B + out[block_end:]

    # 4) Append BLOCK_C
    out = out.rstrip() + "\n\n" + BLOCK_C + "\n"

    OUT_C.write_text(out)
    print(f"Wrote {OUT_C} ({len(out)} bytes, {out.count(chr(10))} lines)")
    print()
    print("Next steps:")
    print(f"  1. Add this line to compile.sh (after the 'sweep' line):")
    print(f"       gcc batch_sweep.c /usr/local/lib/libMN7021aApp.so -lxml2 -lm -lrt -lpthread -fopenmp -o batch_sweep")
    print(f"  2. ./compile.sh")
    print(f"  3. ./batch_sweep")


if __name__ == "__main__":
    main()
