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

## Compare priors on held-out formulas

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/physics-priors-compare
```

The [expression-level labels](../data/catalog/feynman_branches.json) cover all 1,016 benchmark and lecture expressions. The main comparison uses all applicable Codex labels for a fixed evaluation subset of 943 expressions. As a sensitivity check, the scorer also repeats the comparison using only the primary Codex label for each formula in that subset. The [frozen fold plan](../data/priors/feynman_multilabel_folds.json) gives six outer folds and three inner folds for each outer training set. Related formulas and all labels of each formula stay together. Before each fit, the scorer removes training expressions with the same model encoding as an expression in the corresponding evaluation set.

The pooled prior uses each training formula once. Each branch adjustment uses the subset carrying its label, with a fixed 25% geometric mixture. The scorer averages the log probability ratios across applicable branches within each formula. It then averages those formula-level log ratios and exponentiates the overall mean. It also reports the alternative that averages the branch probabilities before taking the log.

The command writes `scores.csv` and `summary.json` to `results/prior_scoring/run/` by default. The CSV contains one row per held-out formula and applicable label in each scheme. Use `--output` to choose a new output directory. The [saved summary](../results/prior_scoring/summary.json) reports 1.34 for the main multilabel comparison and 1.41 for the probability mixture.

The comparison uses the Katz back-off and Good–Turing implementation from [Bartlett and Desmond's Katz repository, pinned revision](https://github.com/DeaglanBartlett/katz/tree/71544a6feafb3162713fcd67a95c24d6616eeb85). The required modules and their [MIT license](../src/physics_priors/priors/_katz/LICENSE) are included with the package. The summaries record known upstream numerical warnings encountered while building the tables. The scorer checks the resulting tables for finite probabilities, valid support and normalization.
