# Development checks

Use Python 3.12 on Linux. The [reproduction guide](reproduction.md) sets up the pinned analysis environment. Run commands from the repository root.

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
.venv/bin/python -m physics_metalaw.catalog --help
.venv/bin/python scripts/exponential_bootstrap.py --help
.venv/bin/python scripts/exponential_coverage_check.py --help
```

### Exercise the analysis pipelines

```bash
.venv/bin/python scripts/exponential_bootstrap.py --boot 32
.venv/bin/python scripts/exponential_coverage_check.py --datasets 2 --boot 8 --workers 1
```

These small runs write to `results/exponential_fit/diagnostics/`. GitHub Actions verifies that both runs write a summary and leave tracked files intact.

GitHub Actions runs the checks on Linux for pull requests to `main` and pushes to `main`. The ongoing PySR experiment uses a separate frozen environment and is outside this workflow.
