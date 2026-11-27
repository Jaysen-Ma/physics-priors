import unittest

import numpy as np

from physics_priors.analysis.sbi_intervals import interval_from_ensemble, ranked_counts, reference_summary


class SBIIntervalTests(unittest.TestCase):
    def test_catalogue_comparison_uses_the_released_wikipedia_subset(self):
        formulas, counts = ranked_counts("wiki")
        self.assertEqual(formulas, 41)
        self.assertEqual(counts.sum(), 553)

    def test_summary_keeps_the_reference_convention_for_one_and_two_ranks(self):
        single = reference_summary(np.array([50]))
        np.testing.assert_array_equal(single, [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1])
        double = reference_summary(np.array([40, 10]))
        self.assertEqual(len(double), 11)
        self.assertEqual(double[-1], 2)
        np.testing.assert_array_equal(double[3:7], [*double[:2], 0, double[2]])
        self.assertAlmostEqual(double[8], np.log(4))

    def test_uniform_density_has_expected_equal_tailed_interval(self):
        grid = np.linspace(0.1, 1.0, 1801)
        # Different log normalizations must not change either member's density.
        summary, density = interval_from_ensemble(
            grid, [np.zeros_like(grid), np.full_like(grid, -300)], [-1.0, 0.0]
        )
        self.assertAlmostEqual(density.sum() * (grid[1] - grid[0]), 1)
        self.assertAlmostEqual(summary["mean"], 0.55)
        self.assertGreater(summary["ensemble_weights"][0], summary["ensemble_weights"][1])
        np.testing.assert_allclose(summary["interval95"], [0.1225, 0.9775], atol=0.0005)
