"""Check the public prior scorer's encoding, grouping, and probability mix."""

import math
import unittest

import numpy as np

from physics_priors.analysis.multilabel_comparison import (
    load_design as load_multilabel_design,
    summarize as summarize_multilabel,
    validated_folds,
)
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

    def test_mix_uses_probabilities_for_whole_equations(self):
        element = EXPERTS.index('geometric_lift')
        scores = np.full(len(EXPERTS), math.log(.2))
        scores[element] = math.log(.8)
        weights = np.zeros(len(EXPERTS))
        weights[0] = 1.
        score = score_mixture({'id': 'example', 'log_scores': scores}, weights)
        self.assertAlmostEqual(score['gain'], math.log((.75 * .2 + .25 * .8) / .2))

    def test_multilabel_folds_separate_groups_and_tree_encodings(self):
        rows, plan, provenance = load_multilabel_design()
        self.assertEqual(len(rows), 943)
        self.assertEqual(provenance['n_catalogue_formulas'], 1016)
        self.assertEqual(provenance['n_labelled'], 967)
        self.assertEqual(provenance['n_multilabel'], 221)
        splits = validated_folds(rows, plan)
        self.assertCountEqual([row['id'] for _, test, _ in splits for row in test],
                              [row['id'] for row in rows])
        for train, test, validation_splits in splits:
            self.assertLess(len(train) + len(test), len(rows))
            for key in ('id', 'group', 'shape'):
                test_values = {row[key] for row in test}
                self.assertTrue(test_values.isdisjoint(row[key] for row in train))
                for fit, validation in validation_splits:
                    self.assertTrue(test_values.isdisjoint(row[key] for row in fit + validation))
                    self.assertTrue({row[key] for row in fit}.isdisjoint(row[key] for row in validation))

    def test_multilabel_aggregations_weight_each_formula_once(self):
        scores = [
            {'id': 'a', 'domain': 'EM', 'gain': math.log(2), 'log_deep_pooled': -3.},
            {'id': 'a', 'domain': 'SR', 'gain': math.log(.5), 'log_deep_pooled': -3.},
            {'id': 'b', 'domain': 'EM', 'gain': math.log(4), 'log_deep_pooled': -3.},
        ]
        summary = summarize_multilabel(scores)
        self.assertEqual((summary['n_formulae'], summary['n_formula_tag_scores']), (2, 3))
        self.assertAlmostEqual(summary['overall_probability_ratio'], 2)
        self.assertAlmostEqual(summary['equal_mixture_probability_ratio'], math.sqrt(5))
