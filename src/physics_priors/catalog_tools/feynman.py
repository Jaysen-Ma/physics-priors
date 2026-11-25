"""Assemble the Feynman benchmark and Lectures for branch analyses."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

import numpy as np
import sympy

from physics_priors.catalog import CATALOG_DIR, scatter_records
from physics_priors.catalog_tools import build_feynman_lectures_catalog as lecture_builder


LABELS = CATALOG_DIR / "feynman_branches.json"

ORDER = ["SR", "QM", "EM", "Waves+optics", "Classical", "Thermo", "Fluid+continuum"]
LONG = {"SR": "Special relativity", "QM": "Quantum mechanics", "EM": "Electromagnetism",
        "Waves+optics": "Waves and optics", "Classical": "Classical mechanics",
        "Thermo": "Thermodynamics and kinetic theory", "Fluid+continuum": "Fluid and continuum mechanics"}

def chapter_from_url(url):
    m = re.search(r"/(I{1,3})_(\d+)\.html", url or "")
    return (m.group(1), int(m.group(2))) if m else None


def corpus_records():
    """Assemble records and their source provenance before joining branch labels."""
    bench = scatter_records("feynman")
    rows = []
    for record in bench:
        volume, chapter = chapter_from_url(record.source_url) or (None, None)
        rows.append((record, dict(source="benchmark", volume=volume,
                                 chapter=chapter, notation=False)))
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
            rows.append((r, dict(source=f"lectures_v{v}", volume=d["volume"],
                                 chapter=d["chapter"], notation=notation)))
    return rows, dict(dedupe), dict(added)


def load_labels(rows, labels_path=LABELS):
    """Validate the Codex annotations against the selected formulas."""
    labels_bytes = labels_path.read_bytes()
    payload = json.loads(labels_bytes)
    labels = payload["records"]
    if Counter(row["id"] for row in labels) != Counter(record.id for record, _ in rows):
        raise ValueError("Codex labels must cover each retained Feynman expression once.")
    pairs = sorted((record.id, record.formula) for record, _ in rows)
    fingerprint = hashlib.sha256(json.dumps(
        pairs, ensure_ascii=False, separators=(",", ":"),
    ).encode()).hexdigest()
    if fingerprint != payload["catalogue_sha256"]:
        raise ValueError("The Feynman formulas differ from the catalogue used for Codex labelling.")

    for row in labels:
        tags, primary = row["branches"], row["primary"]
        if (len(tags) != len(set(tags)) or set(tags) - set(ORDER)
                or (tags and primary not in tags)
                or (not tags and (primary is not None or not row.get("outside")))):
            raise ValueError(f"Invalid Codex branch labels for {row['id']}.")
    return {row["id"]: row for row in labels}, hashlib.sha256(labels_bytes).hexdigest()


def feynman_corpus():
    """Return (record, Codex annotation, source metadata) rows and selection counts."""
    rows, dedupe, added = corpus_records()
    labels, _ = load_labels(rows)
    return [(record, labels[record.id], meta) for record, meta in rows], dedupe, added


def groups_of(rows, *, primary_only=False, drop=None):
    """Map each analysis branch to its expression indices."""
    out = {key: [] for key in ORDER}
    for i, (_record, labels, meta) in enumerate(rows):
        if drop and drop(meta):
            continue
        tags = labels["branches"]
        if primary_only and tags:
            tags = (labels["primary"],)
        for tag in tags:
            out[tag].append(i)
    return {key: np.asarray(indices) for key, indices in out.items() if len(indices) >= 5}
