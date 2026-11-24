"""Check Feynman corpus deduplication, branch sizes, and fitted rates."""
import csv
import json
import unittest

from physics_priors.analysis.exponential_bootstrap import matrix_from_entries
from physics_priors.catalog import CATALOG_DIR, record_as_entry
from physics_priors.catalog_tools import feynman
from physics_priors.catalog_tools.build_feynman_lectures_catalog import BRANCH_OVERRIDE
from physics_priors.exponential_fit import fit_from_type_counts
from physics_priors.paths import ROOT


class FeynmanCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.dedupe, cls.added = feynman.feynman_corpus()
        cls.groups = feynman.groups_of(cls.rows)

    def test_sizes(self):
        self.assertEqual(len(self.rows), 1016)
        self.assertEqual(self.added, {"v1": 278, "v2": 442, "v3": 196})
        self.assertEqual({k: len(v) for k, v in self.groups.items()},
                         {"SR": 89, "QM": 222, "EM": 312, "Waves+optics": 125, "Classical": 105,
                          "Thermo": 73, "Fluid+continuum": 42})

    def test_fixes_applied(self):
        with open(ROOT / "data" / "feynman_lectures_fixes.csv", newline="") as f:
            fixes = {r["id"]: r for r in csv.DictReader(f)}
        recs = {d["id"]: d for v in (1, 2, 3)
                for d in json.loads((CATALOG_DIR / f"feynman_lectures_v{v}.json").read_text())["records"]}
        for i, fx in fixes.items():
            if fx["action"] == "reject":
                self.assertNotIn(i, recs)
            elif fx["action"] == "replace":
                self.assertEqual(recs[i]["formula"], fx["new_formula"])
            elif fx["action"] == "exclude":
                self.assertEqual(recs[i]["consideration"], "out")
        rel = [d for d in recs.values() if (d["volume"], d["chapter"]) in BRANCH_OVERRIDE]
        self.assertTrue(rel)
        self.assertTrue(all(d["branch"] == "Special relativity" for d in rel))

    def test_no_benchmark_double_count(self):
        ids = [r.id for r, _, _ in self.rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_branch_beta(self):
        counts = matrix_from_entries([record_as_entry(r) for r, _, _ in self.rows])
        want = {"SR": 0.382, "QM": 0.328, "EM": 0.324, "Waves+optics": 0.345, "Classical": 0.360,
                "Thermo": 0.403, "Fluid+continuum": 0.422}
        for k, b in want.items():
            result = fit_from_type_counts(counts[self.groups[k]].sum(axis=0))
            self.assertAlmostEqual(result.beta, b, places=3, msg=k)
