"""Build the source-linked astrophysics catalogue from the curated TSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from physics_priors import metalaw
from physics_priors.catalog import (
    CATALOG_DIR, FormulaRecord, _name_occurrences, apply_constants, attach_counts,
)
from physics_priors.paths import ROOT, require_checkout
from physics_priors.priors.encoding import normalized_tree


INPUT = ROOT / "data" / "astrophysics"
CATALOG = CATALOG_DIR / "astrophysics.json"
CONSTANTS = {
    "G", "c", "h", "hbar", "kB", "pc", "pi", "sigma_SB", "sigma_T", "m_e",
    "m_p", "m_H", "a_rad", "e_charge", "zeta_3", "T_sun",
}
TOPICS = {
    "observational_photometry": "Observational photometry",
    "orbital_dynamics": "Orbital dynamics",
    "stellar_structure": "Stellar structure",
    "radiation_transfer": "Radiation and transfer",
    "accretion": "Accretion and outflows",
    "compact_objects": "Compact objects",
    "galaxies": "Galaxies",
    "gravitational_lensing": "Gravitational lensing",
    "cosmological_background": "Cosmological background",
    "thermal_cosmology": "Thermal cosmology",
    "structure_formation": "Structure formation",
    "exoplanets": "Exoplanets",
    "pulsars": "Pulsars",
    "interstellar_intergalactic": "Interstellar and intergalactic medium",
    "star_formation": "Star formation",
}
RELATIONS = {"equals": "=", "approx": "≈", "proportional": "∝", "rhs": "="}
HOLDOUTS = {"expansion_history", "pantheon_distance_relation"}


def build_record(row, source):
    slug, formula = row["id"], row["formula"]
    if not re.fullmatch(r"[a-z][a-z0-9_]*", slug):
        raise ValueError(f"Invalid record ID {slug!r}.")
    if row["role"] not in {"primary", "variant", "related"}:
        raise ValueError(f"{slug}: invalid family role.")
    for name in ("name", "family", "output", "formula", "locator", "notes"):
        if not row[name].strip():
            raise ValueError(f"{slug}: missing {name}.")
    page = int(row["pdf_page"])
    url = urlsplit(source["url"])
    if page < 1 or url.scheme != "https" or not url.netloc or url.fragment:
        raise ValueError(f"{slug}: invalid source or PDF page.")
    reasons = [row["holdout"]] if row["holdout"] else []
    if set(reasons) - HOLDOUTS:
        raise ValueError(f"{slug}: unknown holdout.")
    if row["relation"] == "rhs":
        reasons.append("differential_rhs")

    names = set(_name_occurrences(formula))
    constants = names & CONSTANTS
    rid = f"astrophysics.{slug}"
    formula_record = FormulaRecord(
        corpus="astrophysics", id=rid, original_id=rid, formula=formula,
        original_formula=f"{row['output']} {RELATIONS[row['relation']]} {formula}",
        output=row["output"],
        n_variables=0, n_numbers=0, n_constants=0, complexity=0,
        original_n_variables=0, original_n_numbers=0,
        original_n_constants=0, original_complexity=0,
        status="extension", family=f"astrophysics.{row['family']}", family_role=row["role"],
        representative=row["role"] == "primary", in_released=False, source_kind="pdf",
        source_url=f"{source['url']}#page={page}", source_locator=row["locator"],
        notes=row["notes"], name=row["name"], constant_names=sorted(constants),
        variable_names=sorted(names - constants), consideration="out" if row["relation"] == "rhs" else "in",
        branch="Astronomy and astrophysics",
    )
    attach_counts(apply_constants(formula_record))
    for field in ("n_variables", "n_numbers", "n_constants", "complexity"):
        setattr(formula_record, f"original_{field}", getattr(formula_record, field))
    payload = formula_record.to_json()
    if not payload["tree"] or formula_record.complexity != metalaw.tree_size(payload["tree"]):
        raise ValueError(f"{slug}: tree and operator counts disagree.")
    prior_formula = row["prior_formula"] or formula
    try:
        normalized_tree(prior_formula)
    except (SyntaxError, ValueError) as error:
        raise ValueError(f"{slug}: supply a supported prior encoding or review its inclusion.") from error
    payload.update({
        "topic": TOPICS[row["topic"]],
        "source_id": row["source"],
        "source_citation": source["citation"],
        "pdf_page": page,
        "relation": row["relation"],
        "prior_formula": prior_formula,
        "prior_exclusions": reasons,
        "prior_eligible": not reasons,
    })
    return payload


def build_catalogue() -> dict:
    sources = json.loads((INPUT / "sources.json").read_text(encoding="utf-8"))
    with (INPUT / "formulas.tsv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file, delimiter="\t"))
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("The catalogue must contain unique record IDs.")
    if set(sources) != {row["source"] for row in rows}:
        raise ValueError("The source registry and the formula table use different source IDs.")
    families = {row["family"] for row in rows}
    primary = Counter(row["family"] for row in rows if row["role"] == "primary")
    if families != set(primary) or any(count != 1 for count in primary.values()):
        raise ValueError("Every family must have one primary record.")
    holds = {row["family"] for row in rows if row["holdout"]}
    if any(row["family"] in holds and not row["holdout"] for row in rows):
        raise ValueError("An entire family must share the holdout when any member is held out.")
    return {
        "corpus": "astrophysics",
        "citation": "Source-linked astrophysics and cosmology formula catalogue.",
        "n_records": len(rows),
        "n_families": len(families),
        "policies": ["primary"],
        "sources": sources,
        "records": [build_record(row, sources[row["source"]]) for row in rows],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=CATALOG)
    parser.add_argument("--check", action="store_true", help="Verify the existing catalogue without writing.")
    args = parser.parse_args()
    require_checkout()
    catalogue = build_catalogue()
    payload = json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != payload:
            parser.exit(1, f"Rebuild {args.output} from the curated inputs.\n")
    else:
        args.output.write_text(payload, encoding="utf-8")
    print(f"{args.output}: {catalogue['n_records']} source-linked expressions")


if __name__ == "__main__":
    main()
