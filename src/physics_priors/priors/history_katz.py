"""Katz scoring with the extended tree histories used in the seven-branch study."""

from functools import cache
import math

import numpy as np

from . import model
from .encoding import BINARY, tree_events


def history_events(prefix, size, use_depth):
    """Extend the context while preserving the original tree tokens."""
    nodes = iter(prefix)

    def visit(token, lineage, sibling=None):
        yield lineage, sibling
        if token in model.OPERATORS:
            left = next(nodes)
            yield from visit(left, (*lineage, token))
            if token in BINARY:
                yield from visit(next(nodes), (*lineage, token), left)

    padded = ('None',) * max(size, 2)
    expanded = visit(next(nodes), ())
    for ((side, shallow, detail), target), (lineage, sibling) in zip(
        tree_events(prefix), expanded, strict=True
    ):
        history = (*padded, *lineage)
        if side == 'right':
            history = (*history, sibling if sibling in model.OPERATORS else 'x')
        if history[-2:] != shallow:
            raise ValueError('Extended history changed the shallow encoding.')
        context = history[-size:]
        if use_depth:
            context = (f'depth-{detail[0]}', *context)
        yield side, context, target


def fit_and_score(training, held_out, events):
    """Fit one side-specific model and score each complete held-out tree."""
    samples = {'left': [], 'right': []}
    for ident in training:
        for side, context, word in events[ident]:
            samples[side].append((*context, word))
    backoffs = {side: model.BackOff(phrases) for side, phrases in samples.items()}
    for raw in backoffs.values():
        raw.get_pbo = cache(raw.get_pbo)
        raw.get_alpha = cache(raw.get_alpha)
    normalized = {
        'left': model.NormalisedBackOff(backoffs['left'], model.VOCABULARY),
        'right': model.NormalisedBackOff(backoffs['right'], model.WORDS, follows={'y': 'x'}),
    }

    @cache
    def log_conditional(side, context):
        legal = np.ones(len(model.WORDS), dtype=bool)
        legal[-1] = side == 'right' and context[-1] == 'x'
        probs = np.array([normalized[side].get_pbo(word, context) for word in model.WORDS])
        uniform = legal / legal.sum()
        if not probs.any():
            probs = uniform
        probs = (1.0 - model.UNIFORM_MASS) * probs + model.UNIFORM_MASS * uniform
        model.check_table(probs[None, :], legal[None, :])
        logs = np.log(probs, where=legal, out=np.full_like(probs, -np.inf))
        return dict(zip(model.WORDS, logs, strict=True))

    scores = {
        ident: math.fsum(log_conditional(side, context)[word] for side, context, word in events[ident])
        for ident in held_out
    }
    for raw in backoffs.values():
        raw.get_pbo.cache_clear()
        raw.get_alpha.cache_clear()
    if not all(math.isfinite(score) for score in scores.values()):
        raise ValueError('A Katz fit produced a nonfinite formula score.')
    return scores
