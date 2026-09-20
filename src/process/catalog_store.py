"""Versioned storage and content-hash cache for full-catalog assessment."""
from src.process.catalog_schema import (CATALOG_MODEL, CATALOG_VERSION, CatalogAssessment,
                                        validate_catalog_assessment)
from src.process.db import Phase1CatalogAssessment
from src.process.research_store import utc_now


def current_catalog_assessments(session, rows):
    hashes = {row.id: row.content_hash for row in rows}
    return {
        item.row_id: item
        for item in session.query(Phase1CatalogAssessment).filter_by(version=CATALOG_VERSION)
        if hashes.get(item.row_id) == item.content_hash
    }


def save_catalog_assessment(session, row, result=None, error=None, model=CATALOG_MODEL):
    if result is not None:
        if not isinstance(result, CatalogAssessment):
            result = CatalogAssessment.model_validate(result)
        validate_catalog_assessment(result, row)
    session.merge(Phase1CatalogAssessment(
        row_id=row.id, version=CATALOG_VERSION, content_hash=row.content_hash,
        status='succeeded' if result is not None else 'failed', model=model,
        result_json=result.model_dump_json() if result is not None else None,
        error=error, updated_at=utc_now(),
    ))
    session.commit()
