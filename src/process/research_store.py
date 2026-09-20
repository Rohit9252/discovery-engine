"""Checkpoint research without rewriting source records or hiding failures."""
import hashlib
from datetime import datetime, timezone

from src.process.db import ResearchAnalysis
from src.process.research_schema import ANALYSIS_VERSION, MODEL, RetrievalAssessment, validate_assessment


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def source_hash(review):
    return hashlib.sha256(f'{review.source}\n{review.text}\n{review.url or ""}'.encode('utf-8')).hexdigest()


def current_analysis(session, reviews):
    hashes = {row.id: source_hash(row) for row in reviews}
    return {row.review_id: row for row in session.query(ResearchAnalysis).filter_by(version=ANALYSIS_VERSION)
            if hashes.get(row.review_id) == row.source_hash}


def save_assessment(session, review, result=None, error=None, model=MODEL):
    if result is not None:
        validate_assessment(result, review.text)
        if result.review_id != review.id:
            raise ValueError('Assessment identity does not match source')
    row = ResearchAnalysis(
        review_id=review.id, version=ANALYSIS_VERSION, source_hash=source_hash(review),
        model=model, status='succeeded' if result is not None else 'failed',
        result_json=result.model_dump_json() if result is not None else None,
        error=error, updated_at=utc_now(),
    )
    session.merge(row)
    session.commit()


def decoded_results(analyses):
    return {key: RetrievalAssessment.model_validate_json(row.result_json)
            for key, row in analyses.items() if row.status == 'succeeded'}
