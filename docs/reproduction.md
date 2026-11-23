# Reproduce the operator-frequency analysis

Run these commands from the repository root with Python 3.12 on Linux.

## Set up the environment

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pip check
```

The installed commands use the catalogues in this checkout. The data, ledger files and saved results stay in the repository.

## View the formula ledger locally

```bash
.venv/bin/physics-priors-catalog --serve --port 8766
```

Then open [the local formula ledger](http://127.0.0.1:8766/).

## Run the analysis

The full analysis regenerates saved results and write-up figures. Use a separate checkout if you want to keep the published files for comparison.

Fit the exponential decay rates and compute their bootstrap intervals.

```bash
.venv/bin/physics-priors-fit
```

Run the separate interval-calibration analysis.

```bash
.venv/bin/physics-priors-calibrate
```
