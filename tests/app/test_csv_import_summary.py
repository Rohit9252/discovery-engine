"""The dashboard reports CSV screening separately from AI findings."""
from fastapi.testclient import TestClient

from src.app.api import app
from src.process.db import CsvImportLedger, ReviewMetadata, get_engine, get_session, init_db


def test_dashboard_reconciles_import_ledger(tmp_path, monkeypatch):
    import src.app.api as api
    engine = get_engine(tmp_path / 'reviews.db')
    init_db(engine)
    with get_session(engine) as session:
        session.add(ReviewMetadata(id='csv_one', source='play_store', text='Search cannot find my photo.',
                                   url='https://play.google.com/store/apps/details?id=com.google.android.apps.photos'))
        for identifier, decision in [('one', 'imported'), ('two', 'existing'), ('three', 'held')]:
            session.add(CsvImportLedger(
                row_id=identifier, source_file='combined.csv', source='Google Play Store',
                url='https://example.org/source', original_content='Source text',
                manual_relevance='high', manual_category='search_wrong_results',
                item_type='play_review', disposition=decision, reason='test',
                review_id='csv_one' if decision == 'imported' else None,
                imported_at='2026-09-19T00:00:00Z'))
        session.commit()
    monkeypatch.setattr(api, 'get_engine', lambda: engine)
    response = TestClient(app).get('/api/data')
    assert response.status_code == 200
    assert response.json()['csv_import'] == {
        'positive_rows': 3, 'imported': 1, 'existing': 1, 'held': 1,
    }
