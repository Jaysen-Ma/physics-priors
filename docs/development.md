# Development checks

Use Python 3.12 on Linux. The [reproduction guide](reproduction.md) sets up the pinned analysis environment. Run commands from the repository root.

## Repository layout

| Path | Contents |
| --- | --- |
| [`src/physics_priors/`](../src/physics_priors/) | Installable package with shared expression parsing, operator counting and fitting |
| [`src/physics_priors/analysis/`](../src/physics_priors/analysis/) | Exponential fitting and interval calibration for the write-up |
| [`src/physics_priors/catalog_tools/`](../src/physics_priors/catalog_tools/) | Builds for the Feynman Lectures, Leemis and modified-gravity catalogues |
| [`src/physics_priors/legacy/`](../src/physics_priors/legacy/) | Earlier branch tests, unit checks and plot commands |
| [`scripts/`](../scripts/) | Launchers for running the packaged commands by script path |
| [`data/catalog/`](../data/catalog/) | Checked-in formula catalogues and public ledger |
| [`results/exponential_fit/`](../results/exponential_fit/) | Saved operator-frequency results |
| [`results/legacy/`](../results/legacy/) | Saved results for the earlier analyses |
| [`tests/`](../tests/) and [`writeup/`](../writeup/) | Tests, manuscript source and figures |

The two analysis commands also run at their previous paths directly under `scripts/` after installation. PySR development and run artifacts live in the ignored research workspace.

Legacy commands write their figures and LaTeX tables under `results/legacy/`. The legacy plotting command also refreshes the ledger’s expression-level statistics, so use a separate checkout if you are reproducing the earlier figures.

## Prepare catalogue test fixtures

The catalogue tests rebuild expressions from three CSVs released by Constantin et al. The analysis and formula ledger use the checked-in catalogues. The fixture checkout is only required for the full test suite or for rebuilding those three catalogues from their source.

On a fresh checkout, fetch the published revision and materialise the three input files.

```bash
git clone --filter=blob:none --no-checkout https://github.com/andrei-const/physics-formulae-patterns.git .scratch/physics-formulae-patterns
git -C .scratch/physics-formulae-patterns sparse-checkout set --no-cone /data/Feynman.csv /data/Inflation.csv /data/Wiki.csv
git -C .scratch/physics-formulae-patterns checkout --detach 2aa199b5a1d210dacd122f97c3e8086d3e54f752
```

If the fixture checkout already exists, verify its revision and the three files before running the suite.

## Run the same checks as CI

```bash
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/physics-priors-catalog --help
.venv/bin/physics-priors-fit --help
.venv/bin/physics-priors-calibrate --help
```

### Exercise the analysis pipelines

```bash
.venv/bin/physics-priors-fit --boot 32
.venv/bin/physics-priors-calibrate --datasets 2 --boot 8 --workers 1
```

These small runs write to `results/exponential_fit/diagnostics/`. GitHub Actions verifies that both runs write a summary and leave tracked files intact.

GitHub Actions runs the checks on Linux for pull requests to `main` and pushes to `main`. The ongoing PySR experiment uses a separate frozen environment and is outside this workflow.

## Build the wheel

```bash
.venv/bin/python -m pip wheel --no-deps --wheel-dir dist .
```

CI runs the tests and analysis commands against an installed wheel. To use a wheel locally, install it into the environment in place of the editable install, then run the data-driven commands from the checkout. Shared functions such as expression parsing and operator counting also work outside the checkout.
