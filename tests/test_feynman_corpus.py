"""Check Feynman corpus deduplication, branch sizes, and fitted rates."""
import csv
import json
import tempfile
from pathlib import Path
import unittest

from physics_priors.analysis.exponential_bootstrap import matrix_from_entries
from physics_priors.catalog import CATALOG_DIR, record_as_entry
from physics_priors.catalog_tools import feynman
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
                         {"SR": 87, "QM": 229, "EM": 446, "Waves+optics": 165, "Classical": 117,
                          "Thermo": 96, "Fluid+continuum": 54})
        by_formula = [tags for _, tags, _ in self.rows]
        self.assertEqual(sum(bool(row["branches"]) for row in by_formula), 967)
        self.assertEqual(sum(len(row["branches"]) > 1 for row in by_formula), 221)

    def test_corpus_keeps_chapter_provenance_without_chapter_labels(self):
        for corpus in ("feynman", "feynman_lectures_v1", "feynman_lectures_v2", "feynman_lectures_v3"):
            records = json.loads((CATALOG_DIR / f"{corpus}.json").read_text())["records"]
            self.assertTrue(all("branch" not in record and record["source_url"] for record in records))
        _, labels, meta = next(row for row in self.rows if row[0].id == "III.9.52")
        self.assertIn("QM", labels["branches"])
        self.assertEqual((meta["volume"], meta["chapter"]), ("III", 9))

    def test_label_file_must_cover_every_formula(self):
        rows, _, _ = feynman.corpus_records()
        labels = json.loads(feynman.LABELS.read_text())
        labels["records"][0] = labels["records"][1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "branches.json"
            path.write_text(json.dumps(labels))
            with self.assertRaisesRegex(ValueError, "cover each retained Feynman expression once"):
                feynman.load_labels(rows, path)

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

    def test_no_benchmark_double_count(self):
        ids = [r.id for r, _, _ in self.rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_branch_beta(self):
        counts = matrix_from_entries([record_as_entry(r) for r, _, _ in self.rows])
        want = {"SR": 0.445, "QM": 0.333, "EM": 0.353, "Waves+optics": 0.348, "Classical": 0.373,
                "Thermo": 0.399, "Fluid+continuum": 0.406}
        for k, b in want.items():
            result = fit_from_type_counts(counts[self.groups[k]].sum(axis=0))
            self.assertAlmostEqual(result.beta, b, places=3, msg=k)
