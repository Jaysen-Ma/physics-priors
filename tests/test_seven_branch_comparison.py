"""Checks for the manuscript's seven-branch fold and scoring conventions."""

import copy
import math
import unittest

import numpy as np

from physics_priors.analysis import seven_branch_comparison as compare


class SevenBranchTests(unittest.TestCase):
    def test_frozen_folds_exclude_held_out_groups(self):
        reference = compare.read_json(compare.RESULTS / 'expanded_fluid_cv.json')
        plan = compare.load_frozen_plan(reference)
        self.assertEqual(len(plan['rows']), 1090)
        self.assertEqual(sum(len(row['tags']) for row in plan['rows']), 1273)
        bad_plan = copy.deepcopy(plan)
        fold = bad_plan['folds'][0]
        fold['train'][bad_plan['training']].append(fold['purged'][0])
        with self.assertRaisesRegex(ValueError, 'Fold 1 differs'):
            compare.validate_folds(bad_plan)

    def test_overall_ratio_weights_each_formula_once(self):
        keys = [('g1', 0, 'A'), ('g1', 0, 'B'), ('g2', 0, 'A')]
        pooled = [-5.0, -5.0, -5.0]
        weighted = np.array(pooled) + np.log([4.0, 1.0, 1.0])
        fits = {'h3': (keys, np.array([pooled, weighted]), {})}
        logs, counts = compare.aggregate(fits, ['A', 'B'], (1, 8), np.array([1.0]))
        self.assertEqual(counts, {'A': 2, 'B': 1, 'Overall': 2})
        np.testing.assert_allclose(
            np.exp(logs[0, 1, 0]), [2.0, 1.0, math.sqrt(2.0)], rtol=0, atol=1e-12
        )
