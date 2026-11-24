"""Reproduce the family-grouped comparison of pooled and branch-informed priors."""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import platform
from statistics import mean
import tempfile
import warnings

import numpy as np
import scipy

from physics_priors.catalog_tools import feynman
from physics_priors.paths import ROOT, code_hashes, require_checkout
from physics_priors.priors import model
from physics_priors.priors.encoding import normalized_tree, prefix_labels


PLAN = ROOT / 'data' / 'priors' / 'feynman_folds.json'
OUT = ROOT / 'results' / 'prior_scoring' / 'run'
OUTER_FOLDS = range(5)
INNER_FOLDS = range(3)
SOURCE_FILES = [
    'analysis/prior_comparison.py', 'catalog.py', 'catalog_tools/feynman.py',
    'catalog_tools/build_feynman_lectures_catalog.py', 'priors/encoding.py',
    'priors/model.py', 'priors/_katz/back_off.py', 'priors/_katz/good_turing.py',
]
KATZ_WARNINGS = {
    'divide by zero encountered in scalar divide',
    'invalid value encountered in scalar multiply',
    'invalid value encountered in scalar divide',
}


def labelled_rows():
    corpus, _, _ = feynman.feynman_corpus()
    return sorted(((record.id, feynman.FINE[branch], record.formula)
                   for record, branch, _ in corpus if branch in feynman.FINE),
                  key=lambda row: row[0])


def load_design(plan_path):
    plan = json.loads(plan_path.read_text())
    inputs = labelled_rows()
    fingerprint = hashlib.sha256(json.dumps(
        inputs, ensure_ascii=False, separators=(',', ':'),
    ).encode()).hexdigest()
    if fingerprint != plan['catalogue_sha256']:
        raise ValueError('Catalogue IDs, branch assignments or formulas differ from the frozen study.')
    if plan['geometric_share'] != model.GEOMETRIC_SHARE:
        raise ValueError('The frozen plan and scorer disagree on the geometric mixture share.')
    assignments = [(ident, group) for group, ids in plan['groups'].items() for ident in ids]
    if Counter(ident for ident, _ in assignments) != Counter(ident for ident, _, _ in inputs):
        raise ValueError('The frozen groups must cover every eligible catalogue ID exactly once.')
    group_by_id = dict(assignments)
    rows = [{'id': ident, 'domain': domain, 'group': group_by_id[ident],
             'prefix': prefix_labels(normalized_tree(formula))}
            for ident, domain, formula in inputs]
    domains = sorted(feynman.ORDER)
    groups = set(group_by_id.values())
    seeds = [p['seed'] for p in plan['partitions']]
    if len(seeds) != 4 or len(set(seeds)) != 4:
        raise ValueError('Expected four distinct frozen repetitions.')
    for part in plan['partitions']:
        outer = part['outer']
        if set(outer) != groups or set(outer.values()) != set(OUTER_FOLDS):
            raise ValueError(f"Invalid outer group assignments for repetition {part['seed']}.")
        for fold in OUTER_FOLDS:
            train = [r for r in rows if outer[r['group']] != fold]
            test_domains = {r['domain'] for r in rows if outer[r['group']] == fold}
            inner = part['inner'][str(fold)]
            if (test_domains != set(domains) or set(inner) != {r['group'] for r in train}
                    or set(inner.values()) != set(INNER_FOLDS)):
                raise ValueError(f"Invalid inner group assignments for repetition {part['seed']}, fold {fold}.")
            for slot in INNER_FOLDS:
                fold_domains = {r['domain'] for r in train if inner[r['group']] == slot}
                if fold_domains != set(domains):
                    raise ValueError(f"Inner fold {slot} is missing branches for {part['seed']}/{fold}.")
    return rows, domains, plan


def compare_fold(contexts, domains, train, test, inner):
    validation = []
    for fold in INNER_FOLDS:
        fit = [row for row in train if inner[row['group']] != fold]
        subset = [row for row in train if inner[row['group']] == fold]
        tables = model.fit_experts(contexts, fit, domains)
        validation.extend(model.score_experts(subset, contexts, tables))
    weights = {
        domain: model.learn_weights([row for row in validation if row['domain'] == domain])
        for domain in domains
    }
    tables = model.fit_experts(contexts, train, domains)
    return [
        {key: row[key] for key in ('id', 'group', 'domain')} |
        model.score_mixture(row, weights[row['domain']])
        for row in model.score_experts(test, contexts, tables)
    ]


def summarize(scores, domains):
    by_branch = {domain: mean(row['gain'] for row in scores if row['domain'] == domain)
                 for domain in domains}
    return {'n_scores': len(scores), 'by_branch': by_branch,
            'equal_branch_gain_nats': mean(by_branch.values())}


def compare(plan_path):
    rows, domains, plan = load_design(plan_path)
    contexts = model.Contexts(rows)
    scores, repetitions, notices = [], {}, {}
    katz_path = Path(model.BackOff.get_pbo.__code__.co_filename)
    for part in plan['partitions']:
        seed, outer = part['seed'], part['outer']
        repetition = []
        for fold in OUTER_FOLDS:
            train = [r for r in rows if outer[r['group']] != fold]
            test = [r for r in rows if outer[r['group']] == fold]
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always', RuntimeWarning)
                result = compare_fold(contexts, domains, train, test, part['inner'][str(fold)])
            expected = Counter()
            for warning in caught:
                message = str(warning.message)
                if (warning.category is RuntimeWarning and message in KATZ_WARNINGS
                        and Path(warning.filename) == katz_path):
                    expected[message] += 1
                else:
                    warnings.warn_explicit(message, warning.category, warning.filename, warning.lineno)
            if expected:
                notices[f'{seed}:{fold}'] = dict(expected)
            repetition.extend(dict(row, seed=seed, fold=fold) for row in result)
            print(f'{seed} fold {fold}: scored {len(result)} equations', flush=True)
        if Counter(r['id'] for r in repetition) != Counter(r['id'] for r in rows):
            raise RuntimeError(f'Repetition {seed} did not score each held-out equation exactly once.')
        scores.extend(repetition)
        repetitions[str(seed)] = summarize(repetition, domains)
    return scores, {
        'catalogue_sha256': plan['catalogue_sha256'],
        'fold_plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        'code_sha256': code_hashes(SOURCE_FILES),
        'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'n_equations': len(rows), 'n_groups': len(plan['groups']), 'branches': feynman.LONG,
        'geometric_share': model.GEOMETRIC_SHARE, 'repetitions': repetitions,
        'overall': summarize(scores, domains), 'upstream_katz_warnings': notices,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT,
                        help='new directory for scores.csv and summary.json')
    args = parser.parse_args()
    require_checkout()
    output = args.output.resolve()
    if output.exists():
        parser.error(f'Output directory already exists: {output}. Choose a new --output.')
    scores, summary = compare(PLAN)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        staged = Path(temporary) / 'result'
        staged.mkdir()
        with (staged / 'scores.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(scores[0]))
            writer.writeheader()
            writer.writerows(scores)
        (staged / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
        staged.rename(output)
    print(f"Wrote {len(scores)} scores to {output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
