"""Fit pooled Katz and branch-informed structure probabilities."""

from collections import Counter
from itertools import product
import math

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

from ._katz.back_off import BackOff, NormalisedBackOff
from .encoding import BINARY, UNARY, tree_events


EXPERTS = ('pool', 'direct_depth', 'direct_parent_depth', 'geometric_lift',
           'identity_lift', 'arity_lift', 'full_lift')
GEOMETRIC_SHARE = 0.25
VOCABULARY = ('x', *UNARY, *BINARY)
WORDS = (*VOCABULARY, 'y')
OPERATORS = (*UNARY, *BINARY)
UNIFORM_MASS = 0.001


def shallow_katz(events, rows):
    """Fit the original two-ancestor Katz model separately for each child side."""
    left, right = [], []
    for row in rows:
        for (side, context, _), word in events[row['id']]:
            (left if side == 'left' else right).append((*context, word))
    if not left or not right:
        raise ValueError('Katz training requires both left and right tree events.')
    left_model = NormalisedBackOff(BackOff(left), VOCABULARY)
    right_model = NormalisedBackOff(BackOff(right), WORDS, follows={'y': 'x'})
    result = {}
    left_contexts = (('None', 'None'), *product(('None', *OPERATORS), OPERATORS))
    for side, model, contexts in (
        ('left', left_model, left_contexts),
        ('right', right_model, product(BINARY, VOCABULARY)),
    ):
        for context in contexts:
            probs = np.array([model.get_pbo(word, context) for word in WORDS])
            total = probs.sum()
            if total:
                np.testing.assert_allclose(total, 1.0, rtol=0, atol=1e-12)
            result[side, context] = probs if total else None
    return result


class Contexts:
    """Index the context vocabulary and tree events used in the comparison."""

    def __init__(self, rows, *, keys=None):
        decoded = {row['id']: tree_events(row['prefix']) for row in rows}
        self.keys = sorted({key for events in decoded.values() for key, _ in events}
                           if keys is None else keys)
        context_index = {key: i for i, key in enumerate(self.keys)}
        word_index = {word: i for i, word in enumerate(WORDS)}
        self.decoded = decoded
        self.events = {}
        for ident, events in decoded.items():
            indices = [(context_index[key], word_index[word]) for key, word in events]
            self.events[ident] = tuple(np.asarray(indices).T)
        self.categories = [np.array([word in category for word in WORDS])
                           for category in (('x', 'y'), UNARY, BINARY)]
        sides = sorted({side for side, _, _ in self.keys})
        parents = [(side, context[-1] if side == 'left' else context[0])
                   for side, context, _ in self.keys]
        side_depth = [(side, detail[0]) for side, _, detail in self.keys]
        side = np.array([[1.] + [float(key[0] == s) for s in sides] for key in self.keys])
        depths, unique_parents = sorted(set(side_depth)), sorted(set(parents))
        depth = np.array([[float(value == d) for d in depths] for value in side_depth])
        parent = np.array([[float(value == p) for p in unique_parents] for value in parents])
        self.design_depth = (np.column_stack((side, depth)),
                             np.r_[np.full(side.shape[1], 25.), np.full(depth.shape[1], 60.)])
        self.design_parent = (np.column_stack((side, depth, parent)),
                              np.r_[np.full(side.shape[1], 25.),
                                    np.full(depth.shape[1] + parent.shape[1], 60.)])
        self.support = np.ones((len(self.keys), len(WORDS)), dtype=bool)
        self.support[:, -1] = [side == 'right' and context[-1] == 'x'
                               for side, context, _ in self.keys]
        if any(not self.support[ix].all() for ix in self.events.values()):
            raise ValueError('An encoded expression contains an illegal tree event.')

    def count(self, rows):
        counts = np.zeros(self.support.shape)
        for row in rows:
            np.add.at(counts, self.events[row['id']], 1.)
        return counts

    def smooth_katz(self, raw, fallback=None):
        probabilities = []
        for (side, context, _), legal in zip(self.keys, self.support):
            uniform = legal * (1. / legal.sum())
            dist = raw[side, context]
            if dist is None and fallback is not None:
                dist = fallback[side, context]
            if dist is None:
                dist = uniform
            probabilities.append((1. - UNIFORM_MASS) * dist + UNIFORM_MASS * uniform)
        return np.stack(probabilities)


def check_table(table, support):
    if (table.shape != support.shape or not np.isfinite(table).all()
            or (table[support] <= 0).any() or (table[~support] != 0).any()):
        raise ValueError('A fitted prior has invalid probabilities or grammar support.')
    np.testing.assert_allclose(table.sum(axis=1), 1., rtol=0, atol=1e-12)


def renormalize(table):
    return table / table.sum(axis=1, keepdims=True)


def smoothed(base, counts, strength):
    return (counts + strength * base) / (counts.sum(axis=1, keepdims=True) + strength)


def offsets(base, counts, design):
    features, penalty = design
    n = counts.sum(axis=1)
    used = n > 0
    x, observed, weight = features[used], counts[used], n[used, None]
    legal = base[used] > 0
    logbase = np.log(base[used], where=legal, out=np.full_like(observed, -np.inf))
    shape = (features.shape[1], base.shape[1])

    def objective(flat):
        effect = flat.reshape(shape)
        logits = logbase + x @ effect
        logq = logits - logsumexp(logits, axis=1, keepdims=True)
        neglog = -np.sum(observed[legal] * logq[legal])
        error = weight * np.exp(logq) - observed
        grad = x.T @ error + penalty[:, None] * effect
        return float(neglog + .5 * np.sum(penalty[:, None] * effect**2)), grad.ravel()

    start = np.zeros(math.prod(shape))
    fit = minimize(objective, start, jac=True, method='L-BFGS-B',
                   options={'ftol': 1e-14, 'gtol': 1e-7, 'maxiter': 800})
    gradient = np.linalg.norm(fit.jac, np.inf)
    if not fit.success or gradient >= 1e-3 or fit.fun > objective(start)[0] + 1e-8:
        raise ValueError(f'Branch offset fit failed: {fit.message}, gradient {gradient:g}')
    return renormalize(base * np.exp(features @ fit.x.reshape(shape)))


def lift(base, p, q, power):
    ratio = np.divide(q, p, where=p > 0, out=np.ones_like(base))
    return renormalize(base * ratio**power)


def factor_lifts(base, p, q, categories):
    arity, identity = np.empty_like(base), np.empty_like(base)
    for kind in categories:
        p_mass = p[:, kind].sum(axis=1, keepdims=True)
        q_mass = q[:, kind].sum(axis=1, keepdims=True)
        old = base[:, kind]
        old_mass = old.sum(axis=1, keepdims=True)
        arity[:, kind] = old * q_mass / p_mass
        ratio = np.divide(q[:, kind] * p_mass, p[:, kind] * q_mass, where=p[:, kind] > 0,
                          out=np.ones_like(old))
        new = old * ratio
        identity[:, kind] = new * old_mass / new.sum(axis=1, keepdims=True)
        np.testing.assert_allclose(identity[:, kind].sum(axis=1, keepdims=True), old_mass)
    return renormalize(arity), identity


def learn_weights(rows):
    anchor = np.eye(len(EXPERTS))[0]
    logits = np.stack([r['log_scores'] for r in rows])
    ratios = np.exp(logits - logits.max(axis=1, keepdims=True))
    counts = Counter(r['group'] for r in rows)
    weights = np.array([1 / counts[r['group']] for r in rows])
    # A floor is only used for exponentially tiny intermediate mixture values.
    tiny = np.finfo(float).tiny

    def objective(x):
        prediction = np.maximum(ratios @ x, tiny)
        distance = x - anchor
        value = -weights @ np.log(prediction) + .5 * (distance @ distance)
        grad = -(weights / prediction) @ ratios + distance
        return float(value), grad

    start = .99 * anchor + .01 / len(anchor)
    constraint = {'type': 'eq', 'fun': lambda x: x.sum() - 1,
                  'jac': lambda x: np.ones_like(x)}
    fit = minimize(objective, start, jac=True, method='SLSQP', bounds=[(1e-8, 1)] * len(anchor),
                   constraints=constraint, options={'ftol': 1e-10, 'maxiter': 200})
    if (not fit.success or not np.isclose(fit.x.sum(), 1) or (fit.x <= 0).any()
            or fit.fun > objective(start)[0] + 1e-8):
        raise ValueError(f'Equation mixture fit failed: {fit.message}')
    return fit.x / fit.x.sum()


def fit_experts(contexts, training, domains, *, branch_tags=None):
    """Fit the pooled table and the seven component tables for each branch."""
    if branch_tags is None:
        def branch_tags(row):
            return (row['domain'],)
    pooled = shallow_katz(contexts.decoded, training)
    shallow = contexts.smooth_katz(pooled)
    base = smoothed(shallow, contexts.count(training), 50)
    tables = {}
    for domain in domains:
        subset = [row for row in training if domain in branch_tags(row)]
        counts = contexts.count(subset)
        branch = shallow_katz(contexts.decoded, subset)
        pure = contexts.smooth_katz(branch, fallback=pooled)
        quarter = (1. - GEOMETRIC_SHARE) * shallow + GEOMETRIC_SHARE * pure
        arity, identity = factor_lifts(base, shallow, quarter, contexts.categories)
        bank = {
            'pool': base,
            'direct_depth': offsets(base, counts, contexts.design_depth),
            'direct_parent_depth': offsets(base, counts, contexts.design_parent),
            'geometric_lift': lift(base, shallow, pure, .15),
            'identity_lift': identity,
            'arity_lift': arity,
            'full_lift': lift(base, shallow, pure, 1.),
        }
        for table in bank.values():
            check_table(table, contexts.support)
        tables[domain] = bank
    return tables


def score_experts(rows, contexts, tables):
    for row in rows:
        indices = contexts.events[row['id']]
        bank = tables[row['domain']]
        scores = np.array([math.fsum(np.log(bank[name][indices])) for name in EXPERTS])
        yield {**row, 'log_scores': scores}


def score_mixture(row, weights):
    """Mix whole-equation probabilities and return log gains relative to pooling."""
    scores = row['log_scores']
    pooled = float(scores[0])
    learned = float(logsumexp(scores, b=weights) - pooled)
    geometric = float(scores[EXPERTS.index('geometric_lift')] - pooled)
    gain = float(np.logaddexp(math.log1p(-GEOMETRIC_SHARE) + learned,
                             math.log(GEOMETRIC_SHARE) + geometric))
    if not math.isfinite(gain) or not min(learned, geometric) - 1e-12 <= gain <= max(learned, geometric) + 1e-12:
        raise ValueError(f"Invalid mixture score for {row['id']}")
    return {'log_deep_pooled': pooled, 'learned': learned, 'geometric': geometric, 'gain': gain}
