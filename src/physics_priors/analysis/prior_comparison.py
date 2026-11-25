"""Reproduce the family-grouped comparisons of pooled and branch-informed priors."""

import argparse
import csv
import json
from pathlib import Path
import tempfile

from physics_priors.analysis.multilabel_comparison import compare_multilabel
from physics_priors.paths import ROOT, require_checkout


OUT = ROOT / 'results' / 'prior_scoring' / 'run'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        help='new directory for scores.csv and summary.json')
    args = parser.parse_args()
    require_checkout()
    output = (args.output or OUT).resolve()
    if output.exists():
        parser.error(f'Output directory already exists: {output}. Choose a new --output.')
    scores, summary = compare_multilabel()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        staged = Path(temporary) / 'result'
        staged.mkdir()
        with (staged / 'scores.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(scores[0]))
            writer.writeheader()
            writer.writerows(scores)
        (staged / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
        staged.rename(output)
    print(f"Wrote {len(scores)} scores to {output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
