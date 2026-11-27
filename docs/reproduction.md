# Reproduce the analyses

Run these commands from the repository root with Python 3.12 on Linux.

## Set up the environment

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pip check
```

The installed commands use the catalogues in this checkout. The data, ledger files and saved results stay in the repository.
The [data guide](../data/README.md) describes the catalogue files, record format and correction log.

## View the formula ledger locally

```bash
.venv/bin/physics-priors-catalog --serve --port 8766
```

Then open [the local formula ledger](http://127.0.0.1:8766/).

## Build the catalogs

The checked-in catalogs are the inputs for the analyses below. To rebuild them, prepare the released CSV fixtures using the [development guide](development.md) and run the builders in this order.

```bash
.venv/bin/physics-priors-catalog --seed
.venv/bin/python scripts/catalog/build_feynman_lectures_catalog.py --inputs /path/to/lecture-extraction
.venv/bin/python scripts/catalog/build_fr_catalog.py
.venv/bin/python scripts/catalog/build_leemis_catalog.py
.venv/bin/physics-priors-catalog --refresh-expression-beta
```

The Lectures builder needs the archived `rows_I.json`, `rows_II.json`, and `rows_III.json` extractions. It looks in `.scratch/feynman_v1/` when `--inputs` is omitted. The three extraction files are local, and the existing catalogs are sufficient to reproduce the analyses from a fresh checkout.

The astrophysics catalogue builds from the [checked-in formula table and sources](../data/astrophysics/README.md).

```bash
.venv/bin/python -m physics_priors.catalog_tools.build_astrophysics_catalog
```

## Fit and plot the decay rates

The full analysis regenerates saved results and write-up figures. Use a separate checkout if you want to keep the saved files for comparison.

```bash
.venv/bin/physics-priors-fit
```

This fits the exponential decay rates by log least squares and uses 10,000 whole-equation bootstrap replicates for the individual intervals. The summary's `units` block includes the results and intervals for the constant-convention checks. It compares the original formulas with the operator counts after setting `c = ħ = 1` in the Feynman benchmark and Wikipedia and `M = 1` in Encyclopaedia Inflationaris.

To redraw plots from the saved summary or run the separate interval-calibration check, use these commands.

```bash
.venv/bin/physics-priors-fit --corpus-plot-only --branch-plot-only
.venv/bin/physics-priors-calibrate
```

The saved decay-rate figures and data under `results/exponential_fit/` use the Codex labels. Within each bootstrap replicate, a formula receives one resampling count shared across all of its branches.

The manuscript's main branch figure includes a merged fluid sample of 90 expressions. The [fluid roster](../data/fluid_branch.csv) gives the catalogue IDs for the Feynman and Wikipedia expressions, plus the transcriptions, sources, and variable and constant classifications for the 25 additions. Refit this branch alone with `physics-priors-fit --fluid-branch-only`. The command updates the [fluid decay-rate estimate](../results/exponential_fit/fluid_branch.json) and redraws the figure using the [saved comparison estimates](../results/exponential_fit/branch_plot_reference.json).

## Reproduce the SBI intervals

Use a separate Python 3.12 environment for the simulation-based inference comparison in Section 3.2.1.

```bash
python3.12 -m venv .venv-sbi
.venv-sbi/bin/python -m pip install 'torch==2.14.0' --index-url https://download.pytorch.org/whl/cpu
.venv-sbi/bin/python -m pip install -r requirements-sbi.txt -e .
.venv-sbi/bin/python -m pip check
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv-sbi/bin/physics-priors-sbi-intervals --workers 4
```

The command uses 100 Feynman benchmark expressions, the 41 released Wikipedia expressions, and 70 inflationary potentials. It fixes the number of operator occurrences in each simulation to the corresponding observed total, generates 10,000 rank curves per collection, and learns a posterior over `beta` from the rank-curve summaries. The summaries use ten features from three curve fits and the number of nonzero ranks, as in the authors' released code. The default prior is uniform on `[0.1, 1]`. The 95% credible intervals are the 2.5th and 97.5th posterior percentiles. [Published SBI procedure](https://arxiv.org/html/2408.11065#S4.SS1) · [Reference implementation](https://github.com/andrei-const/physics-formulae-patterns/blob/2aa199b5a1d210dacd122f97c3e8086d3e54f752/ili_zipf.py)

Each run writes a summary and a posterior density grid for each collection to `results/sbi/run/`. Use `--collection` to select one or more collections and `--output` to choose a new directory. Changing `--beta-min` or `--beta-max` changes the prior and regenerates the training simulations. The resulting posterior intervals describe uncertainty under the simulator and the chosen prior.

## Reproduce the seven-branch prior comparison

Run from the checkout using the analysis environment installed above.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/physics-priors-compare-seven-branches --workers 4
```

The [frozen fold plan](../data/priors/seven_branch_folds.json) records all 1,090 formulas, their source IDs, branch labels, reviewed groups, and the ordered expression trees supplied to the model. It lists the exact training and test IDs in each fold. The scorer verifies the plan and excludes every formula in a held-out formula's reviewed group from that fold's training set. Each formula appears in the test set once, together with all its labels. Formulas describing different physical relations can share an encoded tree.

The command refits all ten model variants at eightfold branch weighting and a 25% whole-expression blend. It writes the paired log probabilities by formula and branch and compares the resulting ratios against the [Section 4 reference](../results/prior_scoring/expanded_fluid_cv.json). The output summary also records whether each score file has the archived checksum. Choose a new directory with `--output` for another run. The default is `.scratch/seven_branch_cv/`.

To reproduce the [weight and mixture ablation](../results/prior_scoring/expanded_fluid_ablation.json), add `--ablation --output .scratch/seven_branch_ablation`. This refits the models for the whole weight sweep, verifies the reported appendix values, and saves the full grid.

## Reproduce the earlier Feynman-only comparison

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/physics-priors-compare
```

The [expression-level labels](../data/catalog/feynman_branches.json) cover all 1,016 benchmark and lecture expressions. The main comparison uses all applicable Codex labels for a fixed evaluation subset of 943 expressions. As a sensitivity check, the scorer also repeats the comparison using only the primary Codex label for each formula in that subset. The [frozen fold plan](../data/priors/feynman_multilabel_folds.json) gives six outer folds and three inner folds for each outer training set. Related formulas and all labels of each formula stay together. Before each fit, the scorer removes training expressions with the same model encoding as an expression in the corresponding evaluation set.

The pooled prior uses each training formula once. Each branch adjustment uses the subset carrying its label, with a fixed 25% geometric mixture. The scorer averages the log probability ratios across applicable branches within each formula. It then averages those formula-level log ratios and exponentiates the overall mean. It also reports the alternative that averages the branch probabilities before taking the log.

The command writes `scores.csv` and `summary.json` to `results/prior_scoring/run/` by default. The CSV contains one row per held-out formula and applicable label in each scheme. Use `--output` to choose a new output directory. The [saved summary](../results/prior_scoring/summary.json) reports 1.34 for the main multilabel comparison and 1.41 for the probability mixture.

The comparison uses the Katz back-off and Good–Turing implementation from [Bartlett and Desmond's Katz repository, pinned revision](https://github.com/DeaglanBartlett/katz/tree/71544a6feafb3162713fcd67a95c24d6616eeb85). The required modules and their [MIT license](../src/physics_priors/priors/_katz/LICENSE) are included with the package. The summaries record known upstream numerical warnings encountered while building the tables. The scorer checks the resulting tables for finite probabilities, valid support and normalization.
