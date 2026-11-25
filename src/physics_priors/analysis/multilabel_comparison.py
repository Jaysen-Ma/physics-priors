"""Reproduce the matched Feynman comparison of three branch labelling schemes."""

from collections import Counter, defaultdict
import hashlib
from itertools import product
import json
import math
from pathlib import Path
from statistics import mean
import warnings

from scipy.special import logsumexp

from physics_priors.analysis.prior_comparison import INNER_FOLDS, KATZ_WARNINGS, OUTER_FOLDS
from physics_priors.catalog_tools import feynman
from physics_priors.paths import ROOT
from physics_priors.priors import model
from physics_priors.priors.encoding import normalized_tree, prefix_labels, tree_events


LABELS = ROOT / 'data' / 'priors' / 'feynman_multilabel_labels.json'
FOLDS = ROOT / 'data' / 'priors' / 'feynman_multilabel_folds.json'
DOMAINS = sorted(feynman.ORDER)
SCHEMES = ('earlier', 'fresh_single', 'multilabel')


def load_design(labels_path=LABELS, fold_path=FOLDS):
    labels_bytes, fold_bytes = labels_path.read_bytes(), fold_path.read_bytes()
    labels, plan = json.loads(labels_bytes), json.loads(fold_bytes)
    labels_hash = hashlib.sha256(labels_bytes).hexdigest()
    if labels_hash != plan['labels_sha256'] or plan['geometric_share'] != model.GEOMETRIC_SHARE:
        raise ValueError('The label file or prior mixture differs from the frozen multilabel study.')

    catalogue = {record.id: (record.formula, feynman.FINE.get(branch))
                 for record, branch, _ in feynman.feynman_corpus()[0]}
    records = labels['records']
    if Counter(row['id'] for row in records) != Counter(catalogue.keys()):
        raise ValueError('The label file must cover each retained Feynman expression once.')
    pairs = sorted((ident, formula, branch) for ident, (formula, branch) in catalogue.items())
    fingerprint = hashlib.sha256(json.dumps(
        pairs, ensure_ascii=False, separators=(',', ':'),
    ).encode()).hexdigest()
    if fingerprint != labels['catalogue_sha256']:
        raise ValueError('Feynman expressions or earlier labels differ from the frozen multilabel study.')

    assignments = [(ident, group) for group, ids in plan['groups'].items() for ident in ids]
    matched = [row['id'] for row in records if row['primary'] and catalogue[row['id']][1]]
    if Counter(ident for ident, _ in assignments) != Counter(matched):
        raise ValueError('The frozen groups must cover the matched roster exactly once.')
    by_id = dict(assignments)
    rows = []
    for row in records:
        ident, primary, tags = row['id'], row['primary'], row['branches']
        if (len(tags) != len(set(tags)) or set(tags) - set(DOMAINS)
                or (tags and primary not in tags) or (not tags and primary is not None)):
            raise ValueError(f'Invalid branch labels for {ident}.')
        if ident in by_id:
            formula, earlier = catalogue[ident]
            prefix = prefix_labels(normalized_tree(formula))
            rows.append({'id': ident, 'group': by_id[ident], 'prefix': prefix,
                         'shape': tuple(tree_events(prefix)), 'earlier': [earlier],
                         'fresh_single': [primary], 'multilabel': tags})
    provenance = {
        'n_catalogue_formulas': len(records),
        'n_labelled': sum(bool(row['branches']) for row in records),
        'n_multilabel': sum(len(row['branches']) > 1 for row in records),
        'labels_sha256': labels_hash,
        'fold_plan_sha256': hashlib.sha256(fold_bytes).hexdigest(),
    }
    return rows, plan, provenance


def held_out(rows, assignments, fold):
    """Split by family and purge exact tree encodings from the training side."""
    test = [row for row in rows if assignments[row['group']] == fold]
    test_shapes = {row['shape'] for row in test}
    train = [row for row in rows
             if assignments[row['group']] != fold and row['shape'] not in test_shapes]
    return train, test


def validated_folds(rows, plan):
    def validate_map(rows_to_split, assignment, folds):
        if (set(assignment) != {row['group'] for row in rows_to_split}
                or set(assignment.values()) != set(folds)):
            raise ValueError('Frozen fold assignments must cover every available group.')

    def validate_support(items):
        if any({tag for row in items for tag in row[scheme]} != set(DOMAINS) for scheme in SCHEMES):
            raise ValueError('Every training and evaluation partition must cover all seven branches.')

    outer = plan['outer']
    validate_map(rows, outer, OUTER_FOLDS)
    splits = []
    for fold in OUTER_FOLDS:
        train, test = held_out(rows, outer, fold)
        validate_support(train)
        validate_support(test)
        inner = plan['inner'][str(fold)]
        validate_map(train, inner, INNER_FOLDS)
        validation_splits = [held_out(train, inner, slot) for slot in INNER_FOLDS]
        for fit, validation in validation_splits:
            validate_support(fit)
            validate_support(validation)
        splits.append((train, test, validation_splits))
    return splits


def grammar_context_keys():
    """Enumerate tree contexts from the grammar before seeing held-out data."""
    ops = model.OPERATORS
    yield 'left', ('None', 'None'), (0, 'None')
    for parent in ops:
        yield 'left', ('None', parent), (1, 'None')
    for pair in product(ops, repeat=2):
        yield 'left', pair, (2, 'None')
        for depth, ancestor in product((3, 4), ops):
            yield 'left', pair, (depth, ancestor)
    for pair in product(model.BINARY, model.VOCABULARY):
        yield 'right', pair, (1, 'None')
        for depth, ancestor in product((2, 3, 4), ops):
            yield 'right', pair, (depth, ancestor)


def compare_fold(contexts, scheme, train, test, validation_splits):
    def branch_tags(row):
        return row[scheme]

    def scores(training, evaluation):
        tables = model.fit_experts(contexts, training, DOMAINS, branch_tags=branch_tags)
        pairs = (dict(row, domain=tag) for row in evaluation for tag in branch_tags(row))
        return model.score_experts(pairs, contexts, tables)

    validation_scores = defaultdict(list)
    for fit, validation in validation_splits:
        for row in scores(fit, validation):
            validation_scores[row['domain']].append(row)
    weights = {domain: model.learn_weights(validation_scores[domain]) for domain in DOMAINS}
    return [
        {key: row[key] for key in ('id', 'group', 'domain')} |
        model.score_mixture(row, weights[row['domain']])
        for row in scores(train, test)
    ]


def summarize(scores):
    formulas, branches = defaultdict(list), defaultdict(list)
    for row in scores:
        formulas[row['id']].append(row)
        branches[row['domain']].append(row['gain'])
    usual, mixture, pooled = [], [], []
    for members in formulas.values():
        gains = [row['gain'] for row in members]
        pooled_values = {row['log_deep_pooled'] for row in members}
        if len(pooled_values) != 1:
            raise RuntimeError('A multiply labelled expression must have one pooled score.')
        pooled.append(pooled_values.pop())
        usual.append(mean(gains))
        mixture.append(float(logsumexp(gains)) - math.log(len(gains)))
    return {
        'n_formulae': len(formulas), 'n_formula_tag_scores': len(scores),
        'overall_probability_ratio': math.exp(mean(usual)),
        'equal_mixture_probability_ratio': math.exp(mean(mixture)),
        'mean_pooled_log_probability': mean(pooled),
        'per_domain_ratio': {domain: math.exp(mean(gains)) for domain, gains in sorted(branches.items())},
        'per_domain_n': {domain: len(gains) for domain, gains in sorted(branches.items())},
    }


def compare_multilabel(labels_path=LABELS, fold_path=FOLDS):
    rows, plan, summary = load_design(labels_path, fold_path)
    splits = validated_folds(rows, plan)
    contexts = model.Contexts(rows, keys=grammar_context_keys())
    summary['schemes'] = {}
    result = []
    katz_source = Path(model.BackOff.get_pbo.__code__.co_filename)
    for scheme in SCHEMES:
        scores, sizes, notices = [], {}, {}
        for fold, (train, test, validation) in enumerate(splits):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always', RuntimeWarning)
                fold_scores = compare_fold(contexts, scheme, train, test, validation)
            for warning in caught:
                if (warning.category is not RuntimeWarning or str(warning.message) not in KATZ_WARNINGS
                        or Path(warning.filename) != katz_source):
                    warnings.warn_explicit(warning.message, warning.category, warning.filename, warning.lineno)
            notices[str(fold)] = sum(warning.category is RuntimeWarning and str(warning.message) in KATZ_WARNINGS
                                     and Path(warning.filename) == katz_source for warning in caught)
            scores.extend(dict(row, scheme=scheme, fold=fold) for row in fold_scores)
            sizes[str(fold)] = {'train': len(train), 'test': len(test),
                                'purged': len(rows) - len(train) - len(test)}
            print(f'{scheme} fold {fold}: scored {len(test)} equations', flush=True)
        expected = Counter((row['id'], tag) for row in rows for tag in row[scheme])
        if Counter((row['id'], row['domain']) for row in scores) != expected:
            raise RuntimeError(f'Expected one held-out score per formula and label in {scheme}.')
        summary['schemes'][scheme] = summarize(scores) | {'fold_sizes': sizes, 'katz_notices': notices}
        result.extend(scores)

    pooled = {(row['id'], row['log_deep_pooled']) for row in result}
    if len(pooled) != len(rows):
        raise RuntimeError('The same pooled prior must be used for all labelling schemes on each fold.')
    return result, summary
