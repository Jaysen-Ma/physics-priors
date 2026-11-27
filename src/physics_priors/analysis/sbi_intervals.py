"""Reproduce the matched-data SBI comparison for the three public collections."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import hashlib
from importlib.metadata import version
import json
import math
import multiprocessing
from os import chdir
from pathlib import Path
import platform

import numpy as np
from scipy.optimize import leastsq

from physics_priors import RANDOM_SEED
from physics_priors.paths import ROOT, code_hashes, require_checkout


COLLECTIONS = {
    "feynman": "feynman",
    "wiki_release_41": "wiki",
    "inflation": "inflation",
}
DEFAULT_PRIOR = (0.1, 1.0)
VOCABULARY_SIZE = 1_000
SIMULATIONS = 10_000
GRID_POINTS = 1_801
HOLDOUT_FRACTION = 0.2
TRAIN_ARGS = {"training_batch_size": 64, "learning_rate": 1e-4}
NETWORKS = (
    ("maf", {"hidden_features": 50, "num_transforms": 3}),
    ("maf", {"hidden_features": 50, "num_transforms": 4}),
    ("maf", {"hidden_features": 25, "num_transforms": 5}),
    ("maf", {"hidden_features": 25, "num_transforms": 6}),
    ("mdn", {"hidden_features": 25, "num_components": 3}),
    ("mdn", {"hidden_features": 25, "num_components": 4}),
    ("mdn", {"hidden_features": 50, "num_components": 5}),
    ("mdn", {"hidden_features": 50, "num_components": 6}),
)
REFERENCE = (
    "https://github.com/andrei-const/physics-formulae-patterns/"
    "blob/2aa199b5a1d210dacd122f97c3e8086d3e54f752/ili_zipf.py"
)


def ranked_counts(catalogue: str) -> tuple[int, np.ndarray]:
    from physics_priors.catalog import record_as_entry, scatter_records
    from physics_priors.metalaw import rank_counts

    records = [record for record in scatter_records(catalogue) if record.in_released]
    counts = rank_counts([record_as_entry(record) for record in records])
    if not counts:
        raise ValueError(f"The {catalogue} catalogue contains no released operator counts.")
    return len(records), np.asarray(sorted(counts.values(), reverse=True))


def reference_summary(counts: np.ndarray) -> np.ndarray:
    """Adapt the three summary fits from the CC0 reference code in REFERENCE."""
    ranks = np.arange(1, len(counts) + 1)
    tokens = counts.sum()

    def zipf(amplitude, alpha):
        powers = 1 / np.power(ranks, alpha)
        weights = powers / powers.sum()
        weights /= weights.sum()
        return amplitude * tokens * weights

    def zipf_mandelbrot(amplitude, alpha, offset):
        powers = 1 / np.power(ranks + offset, alpha)
        weights = powers / powers.sum()
        weights /= weights.sum()
        return amplitude * tokens * weights

    def exponential(amplitude, beta):
        weights = np.exp(-beta * ranks)
        weights /= weights.sum()
        return amplitude * tokens * weights

    def fit(model, num_params):
        # The reference fits use count-space residuals and report log-space MSE.
        params, *_ = leastsq(
            lambda p: counts - model(*p), np.ones(num_params), full_output=True, maxfev=800
        )
        error = np.mean(np.power(np.log(model(*params) + 1) - np.log(counts + 1), 2))
        return [*params, error]

    if len(counts) == 1:
        return np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1], dtype=float)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        zipf_fit = fit(zipf, 2)
        if len(counts) == 2:
            zm_fit = [*zipf_fit[:2], 0, zipf_fit[-1]]
        else:
            zm_fit = fit(zipf_mandelbrot, 3)
        exp_fit = fit(exponential, 2)
    return np.array([*zipf_fit, *zm_fit, *exp_fit, len(counts)], dtype=float)


def simulated_training_data(name, tokens, bounds):
    from sklearn.model_selection import train_test_split

    seed = int(hashlib.sha256(f"{name}|exact".encode()).hexdigest()[:8], 16) ^ RANDOM_SEED
    rng = np.random.default_rng(seed)
    theta = rng.uniform(*bounds, size=(SIMULATIONS, 1))
    ranks = np.arange(1, VOCABULARY_SIZE + 1)
    summaries = []
    for beta in theta[:, 0]:
        weights = np.exp(-beta * ranks)
        counts = rng.multinomial(tokens, weights / weights.sum())
        summaries.append(reference_summary(np.sort(counts[counts > 0])[::-1]))
    summaries = np.asarray(summaries)
    if not np.isfinite(summaries).all():
        raise ValueError(f"{name} produced nonfinite simulated summaries. Check the prior range.")
    if np.all(summaries == summaries[0]):
        raise ValueError(f"{name} produced identical summaries. Check the prior range.")
    train, _ = train_test_split(
        np.arange(SIMULATIONS), test_size=HOLDOUT_FRACTION, random_state=RANDOM_SEED
    )
    return summaries[train], theta[train], seed


def train_member(index, *, x, theta, observation, grid):
    import torch
    from ili.dataloaders import NumpyLoader
    from ili.inference import InferenceRunner
    from ili.utils import Uniform, load_nde_sbi

    torch.set_num_threads(1)
    model, options = NETWORKS[index]
    net = load_nde_sbi(engine="NPE", model=model, **options)
    prior = Uniform(low=[grid[0]], high=[grid[-1]], device="cpu")
    runner = InferenceRunner.load(
        backend="sbi", engine="NPE", prior=prior, nets=[net], device="cpu",
        train_args=dict(TRAIN_ARGS), proposal=None, out_dir=None,
    )
    posterior, summaries = runner(loader=NumpyLoader(x=x, theta=theta), seed=RANDOM_SEED)
    estimator = posterior.posteriors[0].posterior_estimator
    with torch.no_grad():
        beta = torch.as_tensor(grid, dtype=torch.float32).reshape(-1, 1, 1)
        condition = torch.as_tensor(observation, dtype=torch.float32).reshape(1, -1)
        log_density = estimator.log_prob(beta, condition=condition).numpy().ravel().astype(float)
    validation = summaries[0]
    return log_density, {
        "model": model,
        "options": options,
        "epochs": len(validation["validation_log_probs"]),
        "best_validation_loss": float(validation["best_validation_loss"][-1]),
    }


def interval_from_ensemble(grid, log_density, validation_losses):
    """Return an equal-tailed 95% interval and the prior-truncated mixture density."""
    spacing = grid[1] - grid[0]
    log_density = np.asarray(log_density, dtype=float)
    losses = np.asarray(validation_losses, dtype=float)
    if not np.isfinite(log_density).all() or not np.isfinite(losses).all():
        raise ValueError("A trained estimator returned nonfinite densities or validation losses.")
    densities = np.exp(log_density - log_density.max(axis=1, keepdims=True))
    densities /= densities.sum(axis=1, keepdims=True) * spacing
    weights = np.exp(losses.min() - losses)
    weights /= weights.sum()
    density = weights @ densities
    # Use the same grid CDF as the matched-data comparison.
    cdf = np.cumsum(density)
    cdf /= cdf[-1]
    lo, hi = np.interp([0.025, 0.975], cdf, grid)
    return {
        "mean": float(np.sum(grid * density) * spacing),
        "interval95": [float(lo), float(hi)],
        "ensemble_weights": weights.tolist(),
    }, density


def run_collection(name, catalogue, grid, workers, output):
    n_formulas, counts = ranked_counts(catalogue)
    tokens = int(counts.sum())
    print(f"{name}: simulating {SIMULATIONS} rank curves for {tokens} operator occurrences", flush=True)
    x, theta, seed = simulated_training_data(name, tokens, (grid[0], grid[-1]))
    observation = reference_summary(counts)
    if not np.isfinite(observation).all():
        raise ValueError(f"The observed summaries for {name} are nonfinite.")
    fit = partial(train_member, x=x, theta=theta, observation=observation, grid=grid)
    # sbi writes TensorBoard logs relative to each worker's current directory.
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
        max_tasks_per_child=1, initializer=chdir, initargs=(output,),
    ) as pool:
        members = list(pool.map(fit, range(len(NETWORKS))))
    log_densities, networks = zip(*members, strict=True)
    posterior, density = interval_from_ensemble(
        grid, log_densities, [network["best_validation_loss"] for network in networks]
    )
    print(f"{name}: posterior mean {posterior['mean']:.6f}, 95% interval "
          f"[{posterior['interval95'][0]:.6f}, {posterior['interval95'][1]:.6f}]", flush=True)
    return {
        "formulas": n_formulas,
        "ranked_counts": counts.tolist(),
        "operator_tokens": tokens,
        "simulation_seed": seed,
        "fitting_and_validation_simulations": len(x),
        "posterior": posterior,
        "networks": list(networks),
    }, density


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", choices=COLLECTIONS, action="append", help="Default: all three.")
    parser.add_argument("--beta-min", type=float, default=DEFAULT_PRIOR[0], help="Uniform prior lower bound.")
    parser.add_argument("--beta-max", type=float, default=DEFAULT_PRIOR[1], help="Uniform prior upper bound.")
    parser.add_argument("--workers", type=int, choices=range(1, len(NETWORKS) + 1), default=1)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "sbi" / "run")
    args = parser.parse_args()
    bounds = (args.beta_min, args.beta_max)
    if not (0 < args.beta_min < args.beta_max and math.isfinite(args.beta_max)):
        parser.error("Require 0 < --beta-min < --beta-max with finite bounds.")
    require_checkout()
    names = dict.fromkeys(args.collection or COLLECTIONS)
    packages = ("numpy", "scipy", "scikit-learn", "torch", "sbi", "ltu-ili", "nflows", "lampe", "zuko")
    try:
        runtime = {package: version(package) for package in packages}
    except ImportError as exc:
        parser.exit(1, f"Install the SBI dependencies in docs/reproduction.md first ({exc}).\n")
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.exit(1, f"Output already exists. Choose a new --output directory: {args.output}\n")
    grid = np.linspace(*bounds, GRID_POINTS)
    settings = {
        "prior": {"distribution": "uniform", "bounds": list(bounds)},
        "seed": RANDOM_SEED,
        "simulations_per_collection": SIMULATIONS,
        "holdout_fraction": HOLDOUT_FRACTION,
        "vocabulary_size": VOCABULARY_SIZE,
        "grid_points": GRID_POINTS,
        "training_args": TRAIN_ARGS,
        "interval": "equal-tailed 95% posterior credible interval",
        "summary_reference": REFERENCE,
    }
    collections = {}
    for name in names:
        result, density = run_collection(name, COLLECTIONS[name], grid, args.workers, args.output)
        collections[name] = result
        np.savez_compressed(args.output / f"{name}.npz", beta=grid, density=density)
    report = {
        "settings": settings,
        "runtime": {"python": platform.python_version(), **runtime},
        "code_sha256": code_hashes(["analysis/sbi_intervals.py", "catalog.py", "metalaw.py"]),
        "collections": collections,
    }
    (args.output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
