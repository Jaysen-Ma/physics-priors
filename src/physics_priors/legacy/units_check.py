#!/usr/bin/env python3
"""Do unit conventions explain the lower β of Encyclopaedia Inflationaris?

β (log least squares, bootstrap 2000, seed 20261013) of
  * the Feynman benchmark and Wikipedia as written, and with c = 1 and ħ = 1;
  * Encyclopaedia Inflationaris as written, and with the amplitude M set to 1 in every potential.
Rewritten formulas are recounted. Writes results/legacy/units_check.json.

    .venv/bin/python scripts/legacy/units_check.py
"""
from __future__ import annotations

import json
from collections import Counter
from physics_priors import catalog as C
from physics_priors import metalaw as M
from physics_priors.paths import ROOT, require_checkout


def entry(record, formula):
    """Entry for a rewritten formula, recounted (as catalog.record_as_entry does for unit modes)."""
    if formula == record.formula:
        return C.record_as_entry(record)
    payload = C._view_payload(record, formula)
    counts = M.count_operators(formula)
    ops = Counter({k: v for k, v in counts.items() if not k.startswith("name:") and k != M.NULLARY_NUMBER})
    return M.EIEntry(name=record.id, formula=formula, n_variables=payload["n_variables"],
                     n_numbers=payload["n_numbers"], n_constants=payload["n_constants"],
                     complexity_declared=payload["complexity"], operator_counts=ops, repaired=False)


def fit(entries):
    d = M.beta_with_errors(entries)
    return dict(n=d["n"], beta=round(d["beta"], 4), boot_sigma=round(d["boot_sigma"], 4),
                fit_sigma=round(d["fit_sigma"], 4))


def main() -> int:
    require_checkout()
    out = {}
    for key in ("feynman", "wiki"):
        recs = C.scatter_records(key)
        rew = [C.rewrite_units(r, "c1_hbar1") for r in recs]
        out[key] = dict(as_written=fit([C.record_as_entry(r) for r in recs]),
                        c1_hbar1=fit([entry(r, f) for r, f in zip(recs, rew)]),
                        n_changed=sum(f != r.formula for r, f in zip(recs, rew)))
    recs = C.scatter_records("inflation")
    rew = [M.set_names_to_one(r.formula, ("M",)) for r in recs]
    out["inflation"] = dict(as_written=fit([C.record_as_entry(r) for r in recs]),
                            M1=fit([entry(r, f) for r, f in zip(recs, rew)]),
                            n_changed=sum(f != r.formula for r, f in zip(recs, rew)))
    print(json.dumps(out, indent=1))
    output = ROOT / "results" / "legacy" / "units_check.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
