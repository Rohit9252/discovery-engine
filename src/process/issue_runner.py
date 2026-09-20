"""Resumable, per-record Part One issue classification with the mini model."""
import argparse
import json
import random
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from types import SimpleNamespace

from dotenv import load_dotenv
from sqlalchemy import text

from src.process.db import (CsvImportLedger, ResearchRun, ResearchRunProgress,
                            get_engine, get_session, init_db)
from src.process.issue_extract import extract_issue, get_issue_llm
from src.process.issue_schema import ISSUE_MODEL, ISSUE_VERSION
from src.process.issue_store import current_issue_analysis, save_issue
from src.process.paths import PROJECT_ROOT
from src.process.research_schema import RetrievalAssessment
from src.process.research_store import current_analysis, utc_now
from src.process.source_audit import active_reviews


def candidate_ids(session, reviews, scope='priority', review_ids=None):
    """Use old labels for scheduling only, never as issue truth."""
    if scope == 'ids':
        allowed = set(review_ids or ())
        return {row.id for row in reviews if row.id in allowed}
    if scope == 'all':
        return {row.id for row in reviews}
    old = current_analysis(session, reviews)
    if scope == 'priority':
        return {
            row.id for row in reviews
            if row.id not in old or old[row.id].status != 'succeeded' or
            RetrievalAssessment.model_validate_json(old[row.id].result_json).relevance != 'unrelated'
        }
    if scope == 'negative_sample':
        negatives = [row for row in reviews if row.id in old and old[row.id].status == 'succeeded'
                     and RetrievalAssessment.model_validate_json(old[row.id].result_json).relevance == 'unrelated']
        groups = {}
        for row in negatives:
            groups.setdefault((row.source, row.id.startswith('csv_')), []).append(row.id)
        sample = set()
        rng = random.Random(19)
        for group in groups.values():
            sample.update(rng.sample(group, min(12, len(group))))
        remainder = sorted({row.id for row in negatives} - sample)
        if len(sample) < 100:
            sample.update(rng.sample(remainder, min(100 - len(sample), len(remainder))))
        return sample
    raise ValueError(f'Unsupported issue scope: {scope}')


def issue_error_code(exc):
    message = str(exc)
    if getattr(exc, 'status_code', None) == 429 or type(exc).__name__ in {'RateLimitError', 'ProviderQuotaError'}:
        return 'provider_rate_limit'
    if 'source span' in message:
        return 'validation_source_span'
    if isinstance(exc, ValueError):
        return 'validation_issue_fields'
    return f'provider_{type(exc).__name__}'


def run_issue_analysis(engine=None, llm=None, workers=4, scope='priority', limit=None, review_ids=None):
    engine = engine or get_engine()
    init_db(engine)
    run_id = uuid.uuid4().hex
    with get_session(engine) as session:
        session.execute(text('BEGIN IMMEDIATE'))
        for run in session.query(ResearchRun).filter_by(version=ISSUE_VERSION, status='running'):
            if run.updated_at > utc_now() - timedelta(minutes=10):
                raise RuntimeError('An issue analysis run is already active')
            run.status = 'interrupted'
            run.error = 'Worker stopped responding; remaining records may be resumed.'
        reviews = active_reviews(session).order_by('id').all()
        selected = candidate_ids(session, reviews, scope, review_ids)
        prior = current_issue_analysis(session, reviews)
        pending = [row for row in reviews if row.id in selected and
                   (row.id not in prior or prior[row.id].status != 'succeeded')]
        if limit is not None:
            pending = pending[:limit]
        if not pending:
            session.commit()
            return {'run_id': None, 'scheduled': 0, 'succeeded': 0, 'failed': 0}
        provenance = {}
        for row in session.query(CsvImportLedger).filter(CsvImportLedger.review_id.isnot(None)):
            provenance.setdefault(row.review_id, {'item_type': row.item_type, 'category': row.manual_category})
        payload = [(SimpleNamespace(id=row.id, source=row.source, text=row.text, url=row.url),
                    provenance.get(row.id, {})) for row in pending]
        session.add(ResearchRun(id=run_id, version=ISSUE_VERSION, status='running',
                                started_at=utc_now(), updated_at=utc_now()))
        session.add(ResearchRunProgress(run_id=run_id, phase='issue_screen', scheduled=len(payload),
                                        completed=0, failed=0))
        session.commit()
    done = failed = 0
    status = 'interrupted'
    error = None
    try:
        llm = llm or get_issue_llm()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(extract_issue, review, llm, meta): review for review, meta in payload}
            for future in as_completed(futures):
                review = futures[future]
                try:
                    result = future.result()
                    failure = None
                    done += 1
                except Exception as exc:
                    result = None
                    failure = issue_error_code(exc)
                    failed += 1
                with get_session(engine) as session:
                    save_issue(session, review, result, error=failure, model=ISSUE_MODEL)
                    run = session.get(ResearchRun, run_id)
                    run.updated_at = utc_now()
                    progress = session.get(ResearchRunProgress, run_id)
                    progress.completed, progress.failed = done + failed, failed
                    session.commit()
                if (done + failed) % 10 == 0 or done + failed == len(payload):
                    print(json.dumps({'run_id': run_id, 'processed': done + failed,
                                      'scheduled': len(payload), 'succeeded': done, 'failed': failed}), flush=True)
        status = 'completed_with_errors' if failed else 'completed'
    except BaseException as exc:
        error = type(exc).__name__
        status = 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed'
        raise
    finally:
        with get_session(engine) as session:
            run = session.get(ResearchRun, run_id)
            run.status, run.error, run.updated_at = status, error, utc_now()
            session.commit()
    return {'run_id': run_id, 'scheduled': len(payload), 'succeeded': done, 'failed': failed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', choices=['priority', 'negative_sample', 'all', 'ids'], default='priority')
    parser.add_argument('--review-id', action='append', dest='review_ids')
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=4)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if args.scope == 'ids' and not args.review_ids:
        parser.error('--scope ids requires at least one --review-id')
    load_dotenv(PROJECT_ROOT / '.env')
    print(json.dumps(run_issue_analysis(workers=args.workers, scope=args.scope,
                                        limit=args.limit, review_ids=args.review_ids)), flush=True)
