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

The saved decay-rate figures and data under `results/exponential_fit/` correspond to the write-up snapshot. Run the full fit to regenerate them from the corrected catalogs.

## Compare priors on held-out formulas

```bash
OPENBLAS_NUM_THREADS=1 .venv/bin/physics-priors-compare
```

The command refits both priors from the same outer training folds of the corrected Feynman catalog. [The frozen fold plan](../data/priors/feynman_folds.json) records the 172 groups and a single division into six folds. We fixed the fold assignments using branch counts before fitting the priors. We adopted the six-part split after comparing it with a three-part split of the same catalogue. Related formulas stay together across each split, and every test fold contains formulas from all seven branches. Each outer training set has its own three inner folds, which are used to learn the mixture weights. The final whole-equation probability mixes 75% learned mixture with 25% geometric adjustment. The reference is the deeper pooled Katz model.

The command writes the 968 held-out scores and summaries to `results/prior_scoring/run/`. Use `--output` to choose a new directory for another run. `gain` is the branch-informed log probability minus the pooled log probability in nats. The headline probability ratio exponentiates the mean gain with each formula weighted equally. The summary also includes the equal-branch mean gain. See the [saved summary](../results/prior_scoring/summary.json) for the reference result.

The scorer uses the Katz back-off and Good–Turing implementation from [Bartlett and Desmond's Katz repository, pinned revision](https://github.com/DeaglanBartlett/katz/tree/71544a6feafb3162713fcd67a95c24d6616eeb85). The required modules and their [MIT license](../src/physics_priors/priors/_katz/LICENSE) are included with the package. The summary records known upstream numerical warnings encountered while building the tables. The scorer checks the resulting tables for finite probabilities, valid support and normalization.
