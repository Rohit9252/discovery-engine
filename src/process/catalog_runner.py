"""Fast, resumable batch assessment for every active Phase 1 catalog row."""
import argparse
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from types import SimpleNamespace

from dotenv import load_dotenv
from sqlalchemy import text

from src.process.catalog_extract import extract_catalog_batch, get_catalog_llm
from src.process.catalog_schema import CATALOG_MODEL, CATALOG_VERSION
from src.process.catalog_store import current_catalog_assessments, save_catalog_assessment
from src.process.db import (Phase1CatalogRow, ResearchRun, ResearchRunProgress,
                            get_engine, get_session, init_db)
from src.process.paths import PROJECT_ROOT
from src.process.research_store import utc_now


def make_batches(rows, max_items=8, max_chars=6500):
    if max_items < 1 or max_chars < 100:
        raise ValueError('Batch limits must be positive')
    batches, current, chars = [], [], 0
    for row in rows:
        length = len(row.text)
        if current and (len(current) == max_items or chars + length > max_chars):
            batches.append(current)
            current, chars = [], 0
        current.append(row)
        chars += length
    if current:
        batches.append(current)
    return batches


def assess_batch(rows, llm, pause=time.sleep):
    """Split malformed batches so one difficult record does not lose its peers."""
    last_error = None
    for attempt in range(3):
        try:
            results = extract_catalog_batch(rows, llm)
            return [(row, result, None) for row, result in zip(rows, results)]
        except Exception as exc:
            last_error = type(exc).__name__
            if isinstance(exc, ValueError):
                break
            if attempt < 2:
                pause(2 ** attempt)
    if len(rows) > 1:
        midpoint = len(rows) // 2
        return assess_batch(rows[:midpoint], llm, pause) + assess_batch(rows[midpoint:], llm, pause)
    return [(rows[0], None, last_error or 'UnknownError')]


def run_catalog_analysis(engine=None, llm=None, workers=6, batch_size=8,
                         max_chars=6500, limit=None, progress_every=50):
    engine = engine or get_engine()
    init_db(engine)
    run_id = uuid.uuid4().hex
    with get_session(engine) as session:
        session.execute(text('BEGIN IMMEDIATE'))
        for run in session.query(ResearchRun).filter_by(version=CATALOG_VERSION, status='running'):
            if run.updated_at > utc_now() - timedelta(minutes=10):
                raise RuntimeError('A catalog analysis run is already active')
            run.status = 'interrupted'
            run.error = 'Previous worker stopped; saved rows can be resumed.'
        rows = session.query(Phase1CatalogRow).filter_by(active=1).order_by(
            Phase1CatalogRow.row_number).all()
        current = current_catalog_assessments(session, rows)
        pending = [row for row in rows if row.id not in current or
                   current[row.id].status != 'succeeded']
        if limit is not None:
            pending = pending[:limit]
        if not pending:
            session.commit()
            return {'scheduled': 0, 'succeeded': 0, 'failed': 0, 'run_id': None}
        payload = [SimpleNamespace(id=row.id, source_type=row.source_type,
                                   source=row.source, url=row.url, text=row.text,
                                   raw_json=row.raw_json, content_hash=row.content_hash)
                   for row in pending]
        batches = make_batches(payload, batch_size, max_chars)
        session.add(ResearchRun(id=run_id, version=CATALOG_VERSION, status='running',
                                started_at=utc_now(), updated_at=utc_now()))
        session.add(ResearchRunProgress(run_id=run_id, phase='catalog_assessment',
                                        scheduled=len(pending), completed=0, failed=0))
        session.commit()
    llm = llm or get_catalog_llm()
    done = failed = 0
    status, error = 'interrupted', None
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(assess_batch, batch, llm) for batch in batches]
            for future in as_completed(futures):
                results = future.result()
                with get_session(engine) as session:
                    for row, result, failure in results:
                        save_catalog_assessment(session, row, result, failure, CATALOG_MODEL)
                        if result is None:
                            failed += 1
                        else:
                            done += 1
                    run = session.get(ResearchRun, run_id)
                    run.updated_at = utc_now()
                    progress = session.get(ResearchRunProgress, run_id)
                    progress.completed, progress.failed = done + failed, failed
                    session.commit()
                if (done + failed) // progress_every != (done + failed - len(results)) // progress_every \
                        or done + failed == len(pending):
                    print(json.dumps({'processed': done + failed, 'scheduled': len(pending),
                                      'succeeded': done, 'failed': failed}), flush=True)
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
    return {'scheduled': len(pending), 'succeeded': done, 'failed': failed, 'run_id': run_id}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=6)
    parser.add_argument('--batch-size', type=int, choices=range(1, 13), default=8)
    parser.add_argument('--max-chars', type=int, default=6500)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / '.env')
    print(json.dumps(run_catalog_analysis(workers=args.workers, batch_size=args.batch_size,
                                          max_chars=args.max_chars, limit=args.limit)), flush=True)
