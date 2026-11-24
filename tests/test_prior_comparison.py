"""Check the public prior scorer's encoding, grouping, and probability mix."""

import math
import unittest

import numpy as np

from physics_priors.analysis.prior_comparison import PLAN, load_design, summarize
from physics_priors.priors.encoding import normalized_tree, prefix_labels, tree_events
from physics_priors.priors.model import EXPERTS, score_mixture


class PriorComparisonTests(unittest.TestCase):
    def test_ordered_events_distinguish_identical_and_different_siblings(self):
        def encode(formula):
            return tree_events(prefix_labels(normalized_tree(formula)))

        for formula, right_word in [('a*a', 'x'), ('b*a', 'y')]:
            self.assertEqual(encode(formula), [
                (('left', ('None', 'None'), (0, 'None')), '*'),
                (('left', ('None', '*'), (1, 'None')), 'x'),
                (('right', ('*', 'x'), (1, 'None')), right_word),
            ])

    def test_frozen_design_covers_reviewed_catalogue(self):
        rows, domains, plan = load_design(PLAN)
        self.assertEqual((len(rows), len(domains), len(plan['groups'])), (968, 7, 172))
        self.assertEqual([part['seed'] for part in plan['partitions']], [7361])
        self.assertEqual(set(plan['partitions'][0]['outer'].values()), set(range(6)))

    def test_formula_and_branch_averages_are_weighted_differently(self):
        scores = [
            {'domain': 'a', 'gain': 1},
            {'domain': 'a', 'gain': 2},
            {'domain': 'b', 'gain': 3},
        ]
        summary = summarize(scores, ['a', 'b'])
        self.assertEqual(summary['equal_formula_gain_nats'], 2)
        self.assertEqual(summary['equal_branch_gain_nats'], 2.25)

    def test_mix_uses_probabilities_for_whole_equations(self):
        element = EXPERTS.index('geometric_lift')
        scores = np.full(len(EXPERTS), math.log(.2))
        scores[element] = math.log(.8)
        weights = np.zeros(len(EXPERTS))
        weights[0] = 1.
        score = score_mixture({'id': 'example', 'log_scores': scores}, weights)
        self.assertAlmostEqual(score['gain'], math.log((.75 * .2 + .25 * .8) / .2))
