"""Assemble the Feynman benchmark and Lectures for branch analyses."""

from __future__ import annotations

import json
import re
from collections import Counter

import numpy as np
import sympy

from physics_priors.catalog import CATALOG_DIR, scatter_records
from physics_priors.catalog_tools import build_feynman_lectures_catalog as lecture_builder


# Fine branch labels (as written in the catalogs) -> analysis groups.
FINE = {"Classical mechanics": "Classical", "Special relativity": "SR", "Electromagnetism": "EM",
        "Waves and optics": "Waves+optics", "Thermodynamics and kinetic theory": "Thermo",
        "Quantum mechanics": "QM", "Fluid mechanics": "Fluid+continuum", "Continuum mechanics": "Fluid+continuum"}
ORDER = ["SR", "QM", "EM", "Waves+optics", "Classical", "Thermo", "Fluid+continuum"]
LONG = {"SR": "Special relativity", "QM": "Quantum mechanics", "EM": "Electromagnetism",
        "Waves+optics": "Waves and optics", "Classical": "Classical mechanics",
        "Thermo": "Thermodynamics and kinetic theory", "Fluid+continuum": "Fluid and continuum mechanics"}

# Sensitivity check: the alternative branch for each chapter flagged ambiguous in the
# chapter-to-branch table (None = no single alternative; the chapter is dropped).
# Relativistic electrodynamics (I.34, II.25, II.26, II.28) is SR in the main mapping
# (lecture_builder.BRANCH_OVERRIDE); its alternative here is electromagnetism.
ALT = {
    ("I", 5): None, ("I", 7): None, ("I", 12): None, ("I", 23): "Electromagnetism",
    ("I", 24): "Electromagnetism", ("I", 25): "Electromagnetism", ("I", 28): "Waves and optics",
    ("I", 31): "Electromagnetism", ("I", 32): "Waves and optics", ("I", 34): "Electromagnetism",
    ("I", 35): None, ("I", 36): None, ("I", 37): "Waves and optics", ("I", 41): "Quantum mechanics",
    ("I", 50): None, ("I", 51): "Fluid mechanics",
    ("II", 1): None, ("II", 10): None, ("II", 11): "Thermodynamics and kinetic theory", ("II", 12): None,
    ("II", 19): None, ("II", 22): None, ("II", 25): "Electromagnetism", ("II", 26): "Electromagnetism",
    ("II", 28): "Electromagnetism", ("II", 32): "Electromagnetism", ("II", 33): "Electromagnetism",
    ("II", 34): "Quantum mechanics", ("II", 35): "Quantum mechanics", ("II", 36): None, ("II", 37): None,
    ("III", 4): "Thermodynamics and kinetic theory", ("III", 13): None, ("III", 14): None,
    ("III", 15): None, ("III", 20): None, ("III", 21): None,
}


def chapter_from_url(url):
    m = re.search(r"/(I{1,3})_(\d+)\.html", url or "")
    return (m.group(1), int(m.group(2))) if m else None


def feynman_corpus():
    """[(record, branch label, meta)] for the benchmark plus deduplicated lecture records."""
    bench = scatter_records("feynman")
    labels = {r["id"]: r.get("branch") for r in json.loads((CATALOG_DIR / "feynman.json").read_text())["records"]}
    def bench_label(r):  # same main-mapping rule for benchmark expressions from relativistic-EM chapters
        b = labels.get(r.id)
        return "Special relativity" if b == "Electromagnetism" and chapter_from_url(r.source_url) in lecture_builder.BRANCH_OVERRIDE else b
    rows = []
    for record in bench:
        volume, chapter = chapter_from_url(record.source_url) or (None, None)
        rows.append((record, bench_label(record), dict(source="benchmark", volume=volume,
                     chapter=chapter, ambiguous=False, notation=False)))
    bench_shape = {(chapter_from_url(r.source_url), lecture_builder.signature(r.formula), lecture_builder.consts(r.formula)) for r in bench}
    seen = set()
    for r in bench:
        try:
            seen.add(sympy.srepr(sympy.sympify(r.formula)))
        except Exception:  # noqa: BLE001
            pass
    dedupe, added = Counter(), Counter()
    for v in (1, 2, 3):
        key = f"feynman_lectures_v{v}"
        raw = {d["id"]: d for d in json.loads((CATALOG_DIR / f"{key}.json").read_text())["records"]}
        for r in scatter_records(key):
            d = raw[r.id]
            if d.get("benchmark_overlap"):
                dedupe[f"v{v}: one of the 100 benchmark expressions"] += 1
                continue
            if (chapter_from_url(r.source_url), lecture_builder.signature(r.formula), lecture_builder.consts(r.formula)) in bench_shape:
                dedupe[f"v{v}: same chapter, shape and constants as a benchmark expression"] += 1
                continue
            try:
                ex = sympy.srepr(sympy.sympify(r.formula))
            except Exception:  # noqa: BLE001
                ex = r.formula
            # III.15.20 adds two spin-wave energies. II.23's identical RHS
            # instead adds electric fields, so both physical relations count.
            if ex in seen and r.id != "flp3.15.20":
                dedupe[f"v{v}: exact duplicate of an earlier expression"] += 1
                continue
            seen.add(ex)
            added[f"v{v}"] += 1
            names = set(d.get("variable_names") or []) | set(re.findall(r"[A-Za-z_]\w*", r.formula))
            notation = any(n.startswith("avg") for n in names) or "i" in names or "I" in names
            rows.append((r, d.get("branch"), dict(source=f"lectures_v{v}", volume=d["volume"], chapter=d["chapter"],
                                                  ambiguous=bool(d.get("ambiguous_chapter")), notation=notation)))
    return rows, dict(dedupe), dict(added)


def groups_of(rows, relabel=None, drop=None):
    """Fine groups -> list of row indices (into rows)."""
    out = {}
    for i, (_record, b, meta) in enumerate(rows):
        if drop and drop(meta, b):
            continue
        if relabel:
            b = relabel(meta, b)
        g = FINE.get(b)
        if g:
            out.setdefault(g, []).append(i)
    return {k: np.array(out[k]) for k in ORDER if k in out and len(out[k]) >= 5}
