"""Reuse completed catalog decisions after a local evidence-rule correction."""
from src.process.catalog_schema import CATALOG_VERSION, CatalogAssessment
from src.process.catalog_store import save_catalog_assessment
from src.process.db import Phase1CatalogAssessment, Phase1CatalogRow, get_engine, get_session


def migrate_catalog_assessments(engine=None, from_version='phase1-catalog-v3'):
    engine = engine or get_engine()
    copied = corrected = 0
    with get_session(engine) as session:
        rows = {row.id: row for row in session.query(Phase1CatalogRow).filter_by(active=1)}
        prior = session.query(Phase1CatalogAssessment).filter_by(
            version=from_version, status='succeeded').all()
        for item in prior:
            row = rows.get(item.row_id)
            if row is None or row.content_hash != item.content_hash:
                continue
            if session.get(Phase1CatalogAssessment, (row.id, CATALOG_VERSION)):
                continue
            result = CatalogAssessment.model_validate_json(item.result_json)
            old_class = result.issue_class
            save_catalog_assessment(session, row, result)
            copied += 1
            corrected += result.issue_class != old_class
    return {'copied': copied, 'corrected_issue_class': corrected}


if __name__ == '__main__':
    import json
    print(json.dumps(migrate_catalog_assessments()))
