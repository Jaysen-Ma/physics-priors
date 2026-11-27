"""Keep the fluid ledger in sync with its source-linked roster."""

import json
import unittest

from physics_priors.catalog_tools.build_fluid_catalog import CATALOGUE, build_catalogue


class FluidCatalogueTests(unittest.TestCase):
    def test_generated_catalogue_contains_only_sourced_additions(self):
        expected = build_catalogue()
        self.assertEqual(expected['n_records'], 25)
        self.assertEqual(json.loads(CATALOGUE.read_text(encoding='utf-8')), expected)
        self.assertTrue(all(row['branch'] == 'Fluid and continuum mechanics'
                            for row in expected['records']))
