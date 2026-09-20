"""Export reproducible evidence and reconciled corpus-level research counts."""
import json
from collections import Counter
from datetime import datetime, timezone

from src.process.db import get_engine, get_session
from src.process.paths import PROJECT_ROOT
from src.process.research_dashboard import apply_research_dashboard, research_snapshot
from src.process.dashboard import build_dashboard
from src.process.source_audit import active_reviews


def build_report(session, reviews):
    status, relevant, results = research_snapshot(session, reviews)
    data, _ = apply_research_dashboard(session, reviews, *build_dashboard(reviews))
    by_id = {row.id: row for row in reviews}
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(), 'status': status,
        'available_by_source': dict(Counter(row.source for row in reviews)),
        'retrieval_by_source': dict(Counter(by_id[key].source for key in relevant)),
        'relevance_counts': dict(Counter(row.relevance for row in results.values())),
        'mechanisms': data['themes'] if results else [],
        'other_retrieval_evidence': data.get('other_retrieval_evidence', []),
        'outcomes': data.get('outcomes', {}), 'evidence_field_counts': data.get('evidence_field_counts', {}),
        'limitations': [
            'Public feedback is a purposive bounded sample, not a representative user survey.',
            'Records, comments and reviews are not independent users or retrieval sessions.',
            'AI relevance and cause labels can be wrong even when their literal source spans are valid.',
            'Missing details are recorded only when explicitly stated; silence cannot establish incomplete memory.',
            'App Store URLs point to the app listing, not individual review permalinks.',
            'The source audit confirms product context; it does not independently authenticate every author or claim.',
        ],
        'evidence': [dict(row.model_dump(), source=by_id[key].source, url=by_id[key].url,
                          source_text=by_id[key].text) for key, row in sorted(relevant.items())],
    }


def export_report():
    engine = get_engine()
    try:
        with get_session(engine) as session:
            reviews = active_reviews(session).order_by('id').all()
            report = build_report(session, reviews)
        directory = PROJECT_ROOT / 'data' / 'research'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f'report-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json'
        content = json.dumps(report, ensure_ascii=False, indent=2)
        path.write_text(content, encoding='utf-8')
        (directory / 'latest-report.json').write_text(content, encoding='utf-8')
        return path, report['status']
    finally:
        engine.dispose()


if __name__ == '__main__':
    path, status = export_report()
    print(json.dumps({'report': str(path), 'status': status}))
