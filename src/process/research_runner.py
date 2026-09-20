"""Run resumable research with durable progress, bounded batches and workers."""
import argparse
import json
import uuid
import re
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

from dotenv import load_dotenv

from src.process.db import ResearchRun, ResearchRunProgress, get_engine, get_session, init_db
from src.process.paths import PROJECT_ROOT
from src.process.research_extract import extract_batch, get_research_llm, BatchValidationError
from src.process.research_schema import ANALYSIS_VERSION, MODEL
from src.process.research_store import current_analysis, save_assessment, utc_now
from src.process.source_audit import active_reviews

REVIEW_MODEL = 'gpt-4.1-mini'
REVIEWED_MODELS = {'gpt-4.1', REVIEW_MODEL}
REVIEW_PATTERN = re.compile(r'\b(search\w*|find|finding|retriev\w*|quer\w*|keyword\w*|ocr|remember\w*|forgot\w*|scroll\w*|faces?|tagging|grouping|albums?|sort\w*|filter\w*)\b', re.I)


def failure_reason(error, review_id):
    """Return a safe, actionable code without copying model output into logs."""
    if isinstance(error, BatchValidationError):
        detail = error.errors.get(review_id, '')
        if 'exact' in detail or 'source span' in detail:
            return 'validation_source_quote_mismatch'
        if 'Incomplete memory' in detail or 'stated year' in detail:
            return 'validation_incomplete_memory_unsupported'
        if 'Failure mechanisms require' in detail:
            return 'validation_failure_cause_unsupported'
        if 'Relevant assessments require' in detail:
            return 'validation_relevant_quote_missing'
        if 'Unrelated feedback' in detail:
            return 'validation_unrelated_has_retrieval_fields'
        return 'validation_other'
    name = type(error).__name__
    if name in {'OpenAIRateLimitError', 'RateLimitError', 'ProviderQuotaError'}:
        return 'provider_rate_limit'
    if isinstance(error, ValueError):
        return 'batch_output_invalid'
    return f'provider_{name}'


def needs_semantic_review(review, saved):
    """Reassess positives, retrieval-language negatives, and any failed records."""
    if saved is None or saved.status != 'succeeded':
        return True
    if saved.model in REVIEWED_MODELS:
        return False
    from src.process.research_schema import RetrievalAssessment
    result = RetrievalAssessment.model_validate_json(saved.result_json)
    return result.relevance != 'unrelated' or bool(REVIEW_PATTERN.search(review.text))


def make_batches(reviews, size=8, char_limit=24000):
    batch, chars = [], 0
    for row in reviews:
        if batch and (len(batch) >= size or chars + len(row.text) > char_limit):
            yield batch
            batch, chars = [], 0
        batch.append(row)
        chars += len(row.text)
    if batch:
        yield batch


def run_research(engine=None, llm=None, workers=4, limit=None, review_candidates=False,
                 batch_size=8, retry_failed=True):
    engine = engine or get_engine()
    init_db(engine)
    run_id = uuid.uuid4().hex
    with get_session(engine) as session:
        # SQLite write lock makes concurrent run admission atomic.
        from sqlalchemy import text
        session.execute(text('BEGIN IMMEDIATE'))
        live = session.query(ResearchRun).filter_by(version=ANALYSIS_VERSION, status='running').all()
        for run in live:
            if run.updated_at > utc_now() - timedelta(minutes=10):
                raise RuntimeError('An analysis run is already active')
            run.status = 'interrupted'
            run.error = 'Previous process stopped responding; unfinished records can be resumed.'
        reviews = active_reviews(session).order_by('id').all()
        existing = current_analysis(session, reviews)
        pending = [row for row in reviews if needs_semantic_review(row, existing.get(row.id))] if review_candidates else [
            row for row in reviews if row.id not in existing or
            (retry_failed and existing[row.id].status != 'succeeded')]
        if limit:
            pending = pending[:limit]
        pending = [SimpleNamespace(id=row.id, source=row.source, text=row.text, url=row.url) for row in pending]
        session.add(ResearchRun(id=run_id, version=ANALYSIS_VERSION, status='running', started_at=utc_now(), updated_at=utc_now()))
        session.add(ResearchRunProgress(run_id=run_id, phase='interpretation_check' if review_candidates else 'initial_analysis', scheduled=len(pending), completed=0, failed=0))
        session.commit()
        session.expunge_all()
    done, failed = 0, 0
    try:
        model = REVIEW_MODEL if review_candidates else MODEL
        llm = llm or get_research_llm(model=model)
        batches = list(make_batches(pending, size=batch_size))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(extract_batch, batch, llm): batch for batch in batches}
            for future in as_completed(futures):
                batch = futures[future]
                caught = None
                try:
                    results, error = future.result(), None
                except Exception as exc:
                    caught = exc
                    results = exc.partial_results if isinstance(exc, BatchValidationError) else {}
                    error = type(exc).__name__
                done += len(results)
                failed += len(batch) - len(results)
                with get_session(engine) as session:
                    for review in batch:
                        result = results.get(review.id)
                        save_assessment(session, review, result,
                                        error=failure_reason(caught, review.id) if result is None and error else None,
                                        model=model)
                    run = session.get(ResearchRun, run_id)
                    run.updated_at = utc_now()
                    progress = session.get(ResearchRunProgress, run_id)
                    progress.completed, progress.failed = done + failed, failed
                    session.commit()
                print(json.dumps({'run_id': run_id, 'succeeded_this_run': done, 'failed_this_run': failed, 'scheduled': len(pending)}), flush=True)
                if error in {'AuthenticationError', 'PermissionDeniedError', 'NotFoundError', 'ProviderQuotaError'}:
                    for remaining in futures:
                        remaining.cancel()
                    raise RuntimeError(f'Provider configuration error: {error}')
        status = 'completed_with_errors' if failed else 'completed'
        error = None
    except BaseException as exc:
        status, error = 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', type(exc).__name__
        raise
    finally:
        with get_session(engine) as session:
            run = session.get(ResearchRun, run_id)
            run.status, run.error, run.updated_at = status, error, utc_now()
            session.commit()
    return {'run_id': run_id, 'succeeded': done, 'failed': failed, 'scheduled': len(pending)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=4)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--batch-size', type=int, choices=range(1, 17), default=8)
    parser.add_argument('--review-candidates', action='store_true', help='Second AI pass over positives, retrieval-language negatives and failures.')
    parser.add_argument('--skip-failed', action='store_true', help='Process unseen records only; leave prior failures for a later pipeline.')
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / '.env')
    print(json.dumps(run_research(workers=args.workers, limit=args.limit, review_candidates=args.review_candidates,
                                  batch_size=args.batch_size, retry_failed=not args.skip_failed)), flush=True)
