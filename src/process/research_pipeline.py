"""Analyze, check candidate interpretation, retry failures and export findings."""
import argparse
import json

from dotenv import load_dotenv

from src.process.paths import PROJECT_ROOT
from src.process.research_runner import run_research
from src.process.research_report import export_report


def run_pipeline(workers=4):
    run_research(workers=workers)
    reviewed = run_research(workers=workers, review_candidates=True)
    if reviewed['failed']:
        run_research(workers=workers, review_candidates=True, batch_size=1)
    path, status = export_report()
    return {'report': str(path), 'status': status}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / '.env')
    print(json.dumps(run_pipeline(workers=args.workers)), flush=True)
