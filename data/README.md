# Equation data

This folder holds the equation catalogs used by the analysis and the formula ledger. Each corpus file records the formulas and their sources. The analysis selects records from these files according to its own inclusion rules.

## Files

| File | Contents |
|---|---|
| [catalog/feynman.json](catalog/feynman.json) | The 100 released AI Feynman benchmark entries, plus catalog-only variants. |
| [catalog/feynman_lectures_v1.json](catalog/feynman_lectures_v1.json), [v2](catalog/feynman_lectures_v2.json), [v3](catalog/feynman_lectures_v3.json) | Expressions extracted from the three volumes of *The Feynman Lectures on Physics*. Lecture records carry chapter and equation references where available. |
| [catalog/inflation.json](catalog/inflation.json) | Inflaton potentials from *Encyclopaedia Inflationaris*. |
| [catalog/fr.json](catalog/fr.json) | Published modified-gravity functions. The 16 Pérez-Romero–Nesseris variants of the same template share a family ID. |
| [catalog/wiki.json](catalog/wiki.json) | The released Wikipedia equations and later additions, including a separate set of quantum-mechanics relations. |
| [catalog/leemis.json](catalog/leemis.json) | Probability densities and mass functions from Leemis and McQueston. Some excluded entries have an empty formula and a note. |
| [catalog/index.html](catalog/index.html) | The browser interface for the formula ledger. |
| [catalog/expression-beta.json](catalog/expression-beta.json) | Derived decay-rate and complexity values for the ledger plots. |
| [catalog_branches.json](catalog_branches.json) | Curated branch labels applied when rebuilding the released Feynman benchmark and Wikipedia catalogs. |
| [priors/feynman_folds.json](priors/feynman_folds.json) | Reviewed formula groups and frozen train/test and inner folds for the prior comparison. |
| [feynman_lectures_fixes.csv](feynman_lectures_fixes.csv) | Manual corrections applied when the three lecture catalogs are built. |

## Record format

Each corpus JSON file contains collection metadata, `n_records`, and a `records` array. The total includes stored records that some analyses exclude.

| Fields | Meaning |
|---|---|
| `id`, `original_id` | The stable catalog identifier and the identifier supplied by the source or extraction. |
| `formula`, `output` | The working expression in Python-style notation, such as `x**2` for a square. When supplied separately, `output` names the quantity the expression describes. Some records store a full relation in `formula`. |
| `original_formula`, `source_url`, `source_locator`, `notes` | Provenance for checking a record. For released benchmarks, `original_formula` preserves the released string. Replaced lecture records keep their earlier extraction in `fix.previous_formula`. |
| `tree`, `latex`, `complexity`, `n_variables`, `n_numbers`, `n_constants` | Derived values for display and checking. The counts are occurrences in the tree. A repeated variable can contribute several occurrences. |
| `branch`, `family`, `family_role`, `representative` | Optional subject and relationship metadata. A family can contain equivalent forms or related variants. An analysis can use these labels to keep related formulas together. |
| `in_released`, `consideration`, `benchmark_overlap` | Selection metadata. `in_released` records membership in the upstream release where applicable. `consideration: "out"` retains a catalog record but excludes it from the corresponding corpus analysis. `benchmark_overlap` helps avoid double-counting a lecture expression and its benchmark counterpart. |

The Feynman catalog files store the branch labels. Benchmark labels are maintained in `catalog_branches.json`. Lecture labels come from the archived extractions and the chapter mapping in the lecture builder. The analysis combines fluid and continuum mechanics into one group and applies the relativistic electrodynamics mapping to the benchmark when assembling it with the Lectures.

## Lecture corrections

The correction CSV uses one row per lecture record. The columns are `id`, `volume`, `action`, `error_type`, `new_formula`, `add_constants`, and `reason`.

| Action | What the builder does |
|---|---|
| `replace` | Uses `new_formula` and rebuilds the tree and counts. |
| `constants` | Treats the names in `add_constants` as constants. Separate multiple names with semicolons. |
| `reject` | Omits the extraction from the generated catalog. |
| `exclude` | Keeps the record with `consideration: "out"` and records the reason. |

The builder applies these corrections to archived extraction inputs from `.scratch/feynman_v1/` by default or the directory passed to `--inputs` and writes the three lecture JSON files. Those extraction inputs are local. A fresh checkout can use the checked-in catalogs directly. Corrections to the separate AI Feynman benchmark, such as the missing square in `III.9.52`, are recorded in the benchmark's catalog code. [Lecture builder](../src/physics_priors/catalog_tools/build_feynman_lectures_catalog.py), [benchmark catalog code](../src/physics_priors/catalog.py)

The catalog checks verify that formulas parse and their stored trees and counts agree with recomputation. Individual source checks use the references in each record. See the [reproduction guide](../docs/reproduction.md) for the analysis workflow.
