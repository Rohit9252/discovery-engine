from fastapi.testclient import TestClient

from src.app.api import app
from src.process.db import ReviewMetadata, get_engine, get_session, init_db
from src.process.issue_store import save_issue
from tests.process.test_issue_runner import issue


def test_dashboard_counts_only_observed_issue_evidence(tmp_path, monkeypatch):
    import src.app.api as api

    engine = get_engine(tmp_path / 'issues.db')
    init_db(engine)
    with get_session(engine) as session:
        rows = [
            ReviewMetadata(id='problem', source='reddit',
                           text='I searched for my dog photos and got only food pictures.',
                           url='https://reddit.com/r/googlephotos/comments/problem'),
            ReviewMetadata(id='praise', source='play_store', text='Memories makes beautiful videos.'),
            ReviewMetadata(id='pending', source='play_store', text='I cannot find the cat photo.'),
        ]
        session.add_all(rows)
        session.commit()
        save_issue(session, rows[0], issue('problem', disposition='retrieval_issue',
                                          issue_quote='got only food pictures', photo_target='my dog photos',
                                          attempted_action='searched for my dog photos',
                                          observed_result='got only food pictures', failure_stage='poor_matches'))
        save_issue(session, rows[1], issue('praise', disposition='context', rationale='Positive Memories report.'))
    monkeypatch.setattr(api, 'get_engine', lambda: engine)
    client = TestClient(app)
    data = client.get('/api/data').json()
    status = data['research_status']
    assert data['analysis_method'] == 'source_grounded_issue_assessment'
    assert (status['retrieval_count'], status['pending_count'], status['context_count']) == (1, 1, 1)
    assert data['themes'] == [{'theme': 'Poor or missing search matches', 'count': 1}]
    cards = client.get('/api/insights').json()['insights']
    assert len(cards) == 1 and cards[0]['evidence_id'] == 'problem'
    evidence = client.get('/api/research/evidence').json()
    assert evidence['total'] == 1 and evidence['records'][0]['review_id'] == 'problem'
    assert client.get('/api/research/evidence?category=direct_memory_issue').json()['total'] == 0
    engine.dispose()
