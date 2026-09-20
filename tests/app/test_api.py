from fastapi.testclient import TestClient

from src.app.api import app
from src.process.db import ReviewMetadata, get_engine, init_db, get_session


def test_storage_default_is_independent_of_working_directory(tmp_path, monkeypatch):
    from src.process.paths import REVIEW_DATABASE
    monkeypatch.chdir(tmp_path)
    engine = get_engine()
    assert engine.url.database == str(REVIEW_DATABASE)


def test_dashboard_counts_and_quotes_share_one_population(tmp_path, monkeypatch):
    import src.app.api as api
    engine = get_engine(tmp_path / 'reviews.db')
    init_db(engine)
    with get_session(engine) as session:
        session.add_all([
            ReviewMetadata(id='a', source='reddit', text='Search cannot find my screenshots.', url='https://reddit.com/comments/a'),
            ReviewMetadata(id='b', source='reddit', text='Am I missing how to switch cameras while filming?'),
            ReviewMetadata(id='c', source='play_store', text='My album organization is confusing.'),
            ReviewMetadata(id='d', source='play_store', text='Everything works great.'),
        ])
        session.commit()
    monkeypatch.setattr(api, 'get_engine', lambda: engine)
    client = TestClient(app)
    data = client.get('/api/data').json()
    insights = client.get('/api/insights').json()
    assert data['total_reviews'] == 4
    assert data['source_breakdown'] == {'reddit': 2, 'play_store': 2}
    assert data['analysis_method'] == 'provisional_keyword_matches'
    assert data['failure_stages'] == []
    assert data['failure_stages_count'] is None
    assert data['research_status']['state'] == 'pending_review'
    assert data['research_status']['validated_retrieval_count'] is None
    assert len(insights['strongest_signal']['pain_points']) >= 3
    assert len(insights['strongest_signal']['opportunities']) >= 3
    counts = {row['theme']: row['count'] for row in data['themes']}
    for card in insights['insights']:
        assert card['review_count'] == counts[card['theme_tag']]
        assert card['evidence_id']
        assert 'validated user reviews' not in card['summary']
        assert 'Not yet validated' in card['summary']
    albums = next(card for card in insights['insights'] if card['theme_tag'] == 'Albums')
    assert albums['quote'] == 'My album organization is confusing.'
    assert 'abandonment' not in insights['strongest_signal']['description']


def test_empty_database_does_not_invent_insights(tmp_path, monkeypatch):
    import src.app.api as api
    engine = get_engine(tmp_path / 'empty.db')
    init_db(engine)
    monkeypatch.setattr(api, 'get_engine', lambda: engine)
    client = TestClient(app)
    assert client.get('/api/data').json()['total_reviews'] == 0
    assert client.get('/api/data').json()['research_status']['state'] == 'no_data'
    assert client.get('/api/insights').json()['insights'] == []


def test_missing_storage_returns_actionable_error(tmp_path, monkeypatch):
    import src.app.api as api
    engine = get_engine(tmp_path / 'missing.db')
    monkeypatch.setattr(api, 'get_engine', lambda: engine)
    response = TestClient(app).get('/api/data')
    assert response.status_code == 503
    assert 'error' in response.json()


def test_static_page_and_health_contract():
    client = TestClient(app)
    assert client.get('/').status_code == 200
    health = client.get('/api/health').json()
    assert health['app'] == 'discovery-engine'
    assert health['version'] == 'baseline-1'
    assert client.head('/api/health').status_code == 200


def test_api_excludes_unconfirmed_context_without_losing_stored_count(tmp_path, monkeypatch):
    import src.app.api as api
    from src.process.db import ReviewExclusion
    engine = get_engine(tmp_path / 'context.db')
    init_db(engine)
    with get_session(engine) as session:
        session.add_all([
            ReviewMetadata(id='good',source='reddit',text='Google Photos search cannot find a screenshot'),
            ReviewMetadata(id='unconfirmed',source='reddit',text='Missing Pixel Bluetooth controls'),
        ])
        session.add(ReviewExclusion(review_id='unconfirmed',reason='Product context unconfirmed'))
        session.commit()
    monkeypatch.setattr(api,'get_engine',lambda:engine)
    client = TestClient(app)
    data = client.get('/api/data').json()
    assert (data['stored_count'],data['total_reviews'],data['excluded_count']) == (2,1,1)
    assert all(card['evidence_id'] != 'unconfirmed' for card in client.get('/api/insights').json()['insights'])
