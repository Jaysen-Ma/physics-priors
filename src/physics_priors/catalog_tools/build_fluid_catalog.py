"""Build the formula ledger's fluid additions from the reviewed branch roster."""

import argparse
import csv
import json
from urllib.parse import urlsplit

from physics_priors import metalaw
from physics_priors.catalog import (
    CATALOG_DIR, FormulaRecord, _name_occurrences, apply_constants, attach_counts,
)
from physics_priors.paths import ROOT, require_checkout


ROSTER = ROOT / 'data' / 'fluid_branch.csv'
CATALOGUE = CATALOG_DIR / 'fluid_additions.json'
CORPUS = 'fluid_additions'
SOURCE = 'Sourced fluid additions'


def build_record(row):
    ident = row['id']
    for field in ('id', 'formula', 'physical_output', 'topic', 'source_locator', 'variables_and_domain'):
        if not row[field].strip():
            raise ValueError(f'{ident}: missing {field}.')
    source = urlsplit(row['source_url'])
    if source.scheme != 'https' or not source.netloc:
        raise ValueError(f'{ident}: expected a public HTTPS source URL.')
    formula = row['formula']
    variables, constants = (set(row[key].split()) for key in ('variable_names', 'constant_names'))
    if variables & constants or variables | constants != _name_occurrences(formula).keys():
        raise ValueError(f'{ident}: the formula needs a complete variable and constant classification.')
    record = FormulaRecord(
        corpus=CORPUS, id=ident, original_id=ident, formula=formula, original_formula=formula,
        output=row['physical_output'], name=row['physical_output'],
        n_variables=0, n_numbers=0, n_constants=0, complexity=0,
        original_n_variables=0, original_n_numbers=0, original_n_constants=0, original_complexity=0,
        status='extension', family=None, family_role=None, representative=True, in_released=False,
        source_kind='pdf' if source.path.endswith('.pdf') else 'html',
        source_url=row['source_url'], source_locator=row['source_locator'],
        notes=row['variables_and_domain'], constant_names=sorted(constants),
        variable_names=sorted(variables), branch='Fluid and continuum mechanics',
    )
    attach_counts(apply_constants(record))
    for field in ('n_variables', 'n_numbers', 'n_constants', 'complexity'):
        setattr(record, f'original_{field}', getattr(record, field))
    result = record.to_json()
    if not result['tree'] or metalaw.tree_size(result['tree']) != record.complexity:
        raise ValueError(f'{ident}: tree size and operator counts disagree.')
    return result | {'topic': row['topic']}


def build_catalogue(roster=ROSTER):
    with roster.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len({row['id'] for row in rows}):
        raise ValueError('The fluid roster contains duplicate formula IDs.')
    additions = [row for row in rows if row['source'] == SOURCE]
    records = [build_record(row) for row in additions]
    if not records:
        raise ValueError('The fluid roster contains no sourced additions.')
    return {
        'corpus': CORPUS, 'citation': 'Source-linked fluid and continuum mechanics additions.',
        'n_records': len(records), 'policies': ['primary'], 'records': records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify the generated catalogue without writing.')
    args = parser.parse_args()
    require_checkout()
    catalogue = build_catalogue()
    payload = json.dumps(catalogue, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not CATALOGUE.is_file() or CATALOGUE.read_text(encoding='utf-8') != payload:
            parser.exit(1, f'Rebuild {CATALOGUE} from {ROSTER}.\n')
    else:
        CATALOGUE.write_text(payload, encoding='utf-8')
    print(f"{CATALOGUE}: {catalogue['n_records']} source-linked expressions")


if __name__ == '__main__':
    main()
