"""Persist issue decisions without altering source reviews or older assessments."""
from src.process.db import IssueAnalysis
from src.process.issue_schema import ISSUE_MODEL, ISSUE_VERSION, IssueAssessment, validate_issue
from src.process.research_store import source_hash, utc_now


def current_issue_analysis(session, reviews):
    hashes = {row.id: source_hash(row) for row in reviews}
    return {
        row.review_id: row
        for row in session.query(IssueAnalysis).filter_by(version=ISSUE_VERSION)
        if hashes.get(row.review_id) == row.source_hash
    }


def save_issue(session, review, result=None, error=None, model=ISSUE_MODEL):
    if result is not None:
        if result.review_id != review.id:
            raise ValueError('Issue decision identity does not match source')
        validate_issue(result, review.text)
    session.merge(IssueAnalysis(
        review_id=review.id, version=ISSUE_VERSION, source_hash=source_hash(review),
        status='succeeded' if result is not None else 'failed', model=model,
        result_json=result.model_dump_json() if result is not None else None,
        error=error, updated_at=utc_now(),
    ))
    session.commit()


def decoded_issues(analyses):
    return {
        key: IssueAssessment.model_validate_json(row.result_json)
        for key, row in analyses.items() if row.status == 'succeeded'
    }
