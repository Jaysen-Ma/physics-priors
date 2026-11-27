"""Refit and verify the seven-branch comparison on the manuscript's frozen folds."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
import math
from pathlib import Path
import warnings

import numpy as np

from physics_priors.analysis.multilabel_comparison import KATZ_WARNINGS
from physics_priors.paths import ROOT, code_hashes, require_checkout
from physics_priors.priors import model
from physics_priors.priors.history_katz import fit_and_score, history_events


FOLDS = ROOT / 'data/priors/seven_branch_folds.json'
RESULTS = ROOT / 'results/prior_scoring'
FIELDS = ('id', 'group', 'fold', 'branch', 'source', 'training', 'pooled', 'adapted')
TOLERANCE = 1e-12
MODEL_FILES = ('priors/encoding.py', 'priors/model.py',
               'priors/_katz/back_off.py', 'priors/_katz/good_turing.py')


def read_json(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_folds(plan):
    """Check the frozen ID assignments and the exclusion of all test relatives."""
    rows = plan['rows']
    by_id = {row['id']: row for row in rows}
    branches = set(plan['branches'])
    fold_count = len(plan['folds'])
    if len(by_id) != len(rows) or {row['fold'] for row in rows} != set(range(fold_count)):
        raise ValueError('The plan needs unique formula IDs and complete fold assignments.')
    for row in rows:
        tags = set(row['tags'])
        if not tags or tags - branches or len(tags) != len(row['tags']):
            raise ValueError(f"Invalid branch labels for {row['id']}.")
    for index, fold in enumerate(plan['folds']):
        test = [row['id'] for row in rows if row['fold'] == index]
        groups = {by_id[ident]['group'] for ident in test}
        outside = [row for row in rows if row['fold'] != index]
        train = [row['id'] for row in outside if row['group'] not in groups]
        purged = [row['id'] for row in outside if row['group'] in groups]
        if (fold['test'], fold['train'][plan['training']], fold['purged']) != (test, train, purged):
            raise ValueError(f'Fold {index + 1} differs from its assignments or exclusions.')
        for split in (train, test):
            if {tag for ident in split for tag in by_id[ident]['tags']} != branches:
                raise ValueError(f'Fold {index + 1} does not cover all branches.')


def load_frozen_plan(reference):
    if digest(FOLDS) != reference['design']['roster_plan_sha256']:
        raise ValueError('The fold file does not match the manuscript result.')
    plan = read_json(FOLDS)
    for path, checksum in code_hashes(MODEL_FILES).items():
        if plan['model_code'][path] != checksum:
            raise ValueError(f'Model source differs from the archived run: {path}')
    settings = reference['design']
    if (len(plan['folds']), plan['settings'], plan['weight'], plan['share']) != (
        settings['folds'], settings['settings'], settings['weight'], settings['blend']
    ):
        raise ValueError('The frozen study settings do not match the reference.')
    validate_folds(plan)
    return plan


def fold_blocks(plan):
    by_id = {row['id']: row for row in plan['rows']}
    for index, fold in enumerate(plan['folds']):
        train, test = fold['train'][plan['training']], fold['test']
        yield index, train, test, [
            (branch, [i for i in train if branch in by_id[i]['tags']],
             [i for i in test if branch in by_id[i]['tags']])
            for branch in plan['branches']
        ]


def fit_variant(name, plan, weights, output):
    by_id = {row['id']: row for row in plan['rows']}
    events = {ident: list(history_events(row['prefix'], *plan['settings'][name]))
              for ident, row in by_id.items()}
    keys, rows, scores = [], [], []
    alpha = plan['share']
    primary = weights.index(plan['weight'])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', RuntimeWarning)
        for fold, train, test, blocks in fold_blocks(plan):
            pooled = fit_and_score(train, test, events)
            for branch, target, held in blocks:
                fits = [pooled] + [fit_and_score(train + target * (weight - 1), held, events)
                                   for weight in weights[1:]]
                for ident in held:
                    values = [fit[ident] for fit in fits]
                    adapted = float(np.logaddexp(math.log1p(-alpha) + values[0],
                                                 math.log(alpha) + values[primary]))
                    row = by_id[ident]
                    keys.append((ident, fold, branch))
                    scores.append(values)
                    rows.append((ident, row['group'], fold, branch, row['source'], plan['training'],
                                 values[0], adapted))
    katz_source = Path(model.BackOff.get_pbo.__code__.co_filename)
    for warning in caught:
        if (warning.category is not RuntimeWarning or Path(warning.filename) != katz_source
                or str(warning.message) not in KATZ_WARNINGS):
            raise RuntimeError(f'Unexpected warning in {name}: {warning.message}')
    path = output / f'{name}.csv'
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        writer.writerows(rows)
    print(f'{name}: {len(rows)} paired scores', flush=True)
    return keys, np.asarray(scores).T, {
        'sha256': digest(path), 'warnings': dict(Counter(str(w.message) for w in caught)),
    }


def aggregate(fits, branches, weights, shares):
    keys = next(iter(fits.values()))[0]
    positions = sorted(range(len(keys)), key=keys.__getitem__)
    ids, _, tags = zip(*(keys[i] for i in positions), strict=True)
    tag_counts = Counter(ids)
    overall_weights = np.array([1 / (len(tag_counts) * tag_counts[i]) for i in ids])
    tag_indices = np.array([branches.index(tag) for tag in tags])
    counts = {b: tags.count(b) for b in branches}
    counts['Overall'] = len(tag_counts)

    shape = (len(fits), len(weights), len(shares), len(branches) + 1)
    averages = np.empty(shape)
    with np.errstate(divide='ignore'):
        log_a = np.log(shares)[:, None]
        log_complement = np.log1p(-shares)[:, None]
    for v, (variant_keys, scores, _) in enumerate(fits.values()):
        if variant_keys != keys or len(set(keys)) != len(keys):
            raise ValueError('The variants must score identical formula and branch pairs once.')
        scores = scores[:, positions]
        for w, delta in enumerate(scores - scores[0]):
            gains = np.logaddexp(log_complement, log_a + delta[None, :])
            averages[v, w, :, -1] = gains @ overall_weights
            for j in range(len(branches)):
                averages[v, w, :, j] = gains[:, tag_indices == j].mean(axis=1)
    return averages, counts


def check_result(actual, expected, key='result'):
    """Compare published aggregates, allowing numerical roundoff across platforms."""
    if isinstance(expected, dict):
        for field, value in expected.items():
            check_result(actual[field], value, f'{key}.{field}')
    elif isinstance(expected, list):
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            check_result(a, e, f'{key}[{i}]')
    elif isinstance(expected, float):
        if not math.isclose(actual, expected, rel_tol=TOLERANCE, abs_tol=TOLERANCE):
            raise ValueError(f'{key}: expected {expected:.16g}, obtained {actual:.16g}.')
    elif actual != expected:
        raise ValueError(f'{key}: expected {expected}, obtained {actual}.')


def summarize_main(plan, reference, fits, averages, counts, weights, shares):
    w, a = weights.index(plan['weight']), list(shares).index(plan['share'])
    main = averages[:, w, a]
    names = [*plan['branches'], 'Overall']
    by_name = {}
    for name, gains in zip(names, main.T, strict=True):
        by_name[name] = {
            'ratio': float(np.exp(gains.mean())), 'n_formulas': counts[name],
            'variants_above_one': int(np.count_nonzero(gains > TOLERANCE)),
            'variant_ratio_range': [math.exp(float(gains.min())), math.exp(float(gains.max()))],
        }
    return {
        'overall': by_name.pop('Overall'), 'by_branch': by_name,
        'mean_log_ratios_by_variant': {
            name: {'overall': float(gains[-1]), 'by_branch': dict(zip(names[:-1], gains[:-1], strict=True))}
            for name, gains in zip(fits, main, strict=True)
        },
        'score_files': {
            name: receipt | {'matches_archived_sha256':
                receipt['sha256'] == reference['design']['score_sha256_by_variant'][name]}
            for name, (_, _, receipt) in fits.items()
        },
    }


def write_ablation(output, branches, weights, shares, averages, reference):
    names = [*branches, 'Overall']
    ratios = np.exp(averages.mean(axis=0))
    wins = (averages > TOLERANCE).sum(axis=0)

    def setting(w, a):
        return {
            'weight': weights[w], 'mixture_share': float(shares[a]), 'ratio': float(ratios[w, a, -1]),
            'by_branch': dict(zip(branches, ratios[w, a, :-1], strict=True)),
            'variants_above_one': dict(zip(names, wins[w, a].tolist(), strict=True)),
        }

    shown = reference['table']['shares']
    selected = [list(shares).index(share) for share in shown]
    peak = np.unravel_index(np.argmax(ratios[:, :, -1]), ratios.shape[:2])
    main = reference['main_setting']
    report = {
        'table': {'shares': shown, 'rows': [
            {'weight': weight, 'overall_ratios': ratios[i, selected, -1].tolist()}
            for i, weight in enumerate(weights)
        ]},
        'main_setting': setting(weights.index(main['weight']), list(shares).index(main['mixture_share'])),
        'weighted_fit_without_pooling': setting(weights.index(main['weight']), len(shares) - 1),
        'largest_overall_ratio_on_grid': setting(*peak),
    }
    check_result(report, {field: reference[field] for field in report}, 'ablation')
    path = output / 'ablation.csv'
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['training_weight', 'mixture_share', *(f'{b}_ratio' for b in names),
                         *(f'{b}_variants_above_one' for b in names)])
        for w, weight in enumerate(weights):
            for a, share in enumerate(shares):
                writer.writerow([weight, share, *ratios[w, a], *wins[w, a]])
    report['matches_archived_grid_sha256'] = digest(path) == reference['grid_sha256']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.scratch/seven_branch_cv',
                        help='New output directory (default: .scratch/seven_branch_cv).')
    parser.add_argument('--workers', type=int, default=1, help='Concurrent model variants.')
    parser.add_argument('--ablation', action='store_true', help='Also reproduce the weight and mixture sweep.')
    args = parser.parse_args()
    require_checkout()
    reference = read_json(RESULTS / 'expanded_fluid_cv.json')
    plan = load_frozen_plan(reference)
    if not 1 <= args.workers <= len(plan['settings']):
        parser.error(f"--workers must be between 1 and {len(plan['settings'])}.")
    ablation = read_json(RESULTS / 'expanded_fluid_ablation.json') if args.ablation else None
    weights, shares = (1, plan['weight']), np.array([plan['share']])
    if ablation:
        design = ablation['design']
        if design['main_plan_sha256'] != reference['design']['roster_plan_sha256']:
            raise ValueError('The ablation uses a different fold file.')
        weights = tuple(design['weights'])
        grid = design['mixture_grid']
        shares = np.linspace(grid['minimum'], grid['maximum'], grid['size'])
    try:
        args.output.mkdir(parents=True)
    except FileExistsError:
        parser.error(f'Output already exists: {args.output}. Choose a new directory.')
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs = {name: pool.submit(fit_variant, name, plan, weights, args.output)
                for name in plan['settings']}
        fits = {name: job.result() for name, job in jobs.items()}
    scores, counts = aggregate(fits, plan['branches'], weights, shares)
    summary = summarize_main(plan, reference, fits, scores, counts, weights, shares)
    check_result(summary, {field: reference[field] for field in
                           ('overall', 'by_branch', 'mean_log_ratios_by_variant')})
    if ablation:
        summary['ablation'] = write_ablation(args.output, plan['branches'], weights, shares, scores, ablation)
    summary['fold_plan_sha256'] = digest(FOLDS)
    summary['verified'] = True
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(f"Verified {summary['overall']['ratio']:.9f}× overall across {counts['Overall']:,} formulas.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
