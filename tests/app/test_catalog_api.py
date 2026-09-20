from fastapi.testclient import TestClient

from src.app.api import app
from src.process.catalog_schema import CatalogAssessment
from src.process.catalog_store import save_catalog_assessment
from src.process.db import Phase1CatalogRow, get_engine, get_session, init_db


def test_full_catalog_progress_reaches_dashboard_and_chat(tmp_path, monkeypatch):
    import src.app.api as api

    engine = get_engine(tmp_path / 'catalog-api.db')
    init_db(engine)
    kinds = ['existing_in_scope_evidence', 'web_atomic_evidence', 'web_grounded_scenario']
    with get_session(engine) as session:
        rows = []
        for number, kind in enumerate(kinds, 1):
            row = Phase1CatalogRow(
                id=f'phase1_{number:05d}', row_number=number,
                source_file='catalog.csv', source_type=kind, source='Community',
                url='https://example.org', text='Search returned nothing.',
                raw_json='{}', content_hash=f'hash-{number}', active=1,
                imported_at='now')
            session.add(row)
            rows.append(row)
        session.commit()
        result = CatalogAssessment(
            row_id=rows[0].id, search_relevance='yes',
            issue_class='observed_retrieval_issue', target_media=['photo'],
            remembered_clues=['person', 'place'], forgotten_details=[], search_methods=['keyword'],
            observed_symptoms=['no_results'], journey_stages=['matching_or_coverage', 'evaluating_results'],
            issue_quote='Search returned nothing.', remembered_quote=None,
            forgotten_quote=None, action_quote=None,
            result_quote='Search returned nothing.', confidence='high',
            summary='Search returned no photos.')
        save_catalog_assessment(session, rows[0], result)
    monkeypatch.setattr(api, 'get_engine', lambda: engine)
    client = TestClient(app)
    data = client.get('/api/data').json()
    assert data['stored_count'] == data['total_reviews'] == 3
    assert data['cleaned_count'] == 1
    assert data['catalog_types'] == dict(zip(kinds, [1, 1, 1]))
    assert data['research_status']['pending_count'] == 2
    assert data['themes'] == [{'theme': 'Search returns no photos', 'count': 1}]
    assert data['remembered_clues'] == [
        {'clue': 'Person', 'count': 1},
        {'clue': 'Place', 'count': 1},
    ]
    assert data['journey_stages'] == [
        {'stage': 'Finding a match', 'count': 1},
        {'stage': 'Checking results', 'count': 1},
    ]
    assert client.get('/api/insights').json()['insights'] == []
    monkeypatch.setenv('OPENAI_API_KEY', '')
    chat = client.post('/api/chat', json={'question': 'Why do people struggle to retrieve photos?'}).json()
    assert 'OPENAI_API_KEY' in chat['error']
    assert client.get('/api/research/evidence').json()['analysis_status'] == 'catalog_relevance_check_pending'
    engine.dispose()
