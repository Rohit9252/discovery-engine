"""Reuse validated issue decisions when the exact public source record is reimported."""

import argparse
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.process.db import IssueAnalysis, ReviewMetadata, get_engine, get_session, init_db
from src.process.issue_schema import ISSUE_VERSION, IssueAssessment, validate_issue
from src.process.paths import PROJECT_ROOT
from src.process.research_store import source_hash, utc_now


OLD_DB_PATH = PROJECT_ROOT / 'data' / 'processed' / 'reviews-old-awaiting-verification.db'


def transfer_exact_decisions(old_db_path=OLD_DB_PATH, new_engine=None):
    """Copy succeeded decisions only when source, text, and URL match exactly."""
    old_engine = create_engine(f'sqlite:///{Path(old_db_path).resolve()}')
    new_engine = new_engine or get_engine()
    init_db(new_engine)
    counts = Counter()
    try:
        OldSession = sessionmaker(bind=old_engine)
        with OldSession() as old_session, get_session(new_engine) as new_session:
            old_records = {row.id: row for row in old_session.query(ReviewMetadata)}
            exact = {}
            for row in old_session.query(IssueAnalysis).filter_by(version=ISSUE_VERSION, status='succeeded'):
                source = old_records.get(row.review_id)
                if source and row.source_hash == source_hash(source):
                    exact[(source.source, source.text, source.url)] = row
            prior = {(row.review_id, row.version) for row in new_session.query(IssueAnalysis)}
            for review in new_session.query(ReviewMetadata):
                if (review.id, ISSUE_VERSION) in prior:
                    counts['already_present'] += 1
                    continue
                old = exact.get((review.source, review.text, review.url))
                if old is None:
                    counts['not_reusable'] += 1
                    continue
                decision = IssueAssessment.model_validate_json(old.result_json)
                decision.review_id = review.id
                validate_issue(decision, review.text)
                new_session.add(IssueAnalysis(
                    review_id=review.id, version=ISSUE_VERSION,
                    source_hash=source_hash(review), status='succeeded',
                    model=old.model, result_json=decision.model_dump_json(),
                    error=None, updated_at=utc_now(),
                ))
                counts['reused'] += 1
            new_session.commit()
        return dict(counts)
    finally:
        old_engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-db', type=Path, default=OLD_DB_PATH)
    args = parser.parse_args()
    print(json.dumps(transfer_exact_decisions(args.old_db), indent=2))
