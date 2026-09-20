from fastapi.testclient import TestClient

from src.app.api import app
from src.process.db import ReviewMetadata, ResearchRun, ReviewExclusion, get_engine, get_session, init_db
from src.process.research_schema import ANALYSIS_VERSION
from src.process.research_store import save_assessment, utc_now
from tests.process.test_research import assessment


def test_saved_research_drives_counts_cards_and_evidence(tmp_path, monkeypatch):
    import src.app.api as api
    engine = get_engine(tmp_path / 'research.db')
    init_db(engine)
    with get_session(engine) as session:
        rows = [ReviewMetadata(id='a',source='reddit',text='I remember a red car but forgot the date. Search finds nothing.',url='https://reddit.com/comments/a'),
                ReviewMetadata(id='b',source='play_store',text='Great backup app.'),
                ReviewMetadata(id='excluded',source='reddit',text='Search finds nothing.')]
        session.add_all(rows)
        session.add(ReviewExclusion(review_id='excluded',reason='Unconfirmed context'))
        session.commit()
        for row in [rows[0],rows[2]]:
            item = assessment(row.id,relevance='retrieval',evidence_quotes=['Search finds nothing.'],outcome='failure',failure_mechanism='poor_matches',failure_evidence='Search finds nothing.')
            if row.id=='a':
                item.relevance='incomplete_memory'; item.remembered_clues=['a red car']; item.missing_details=['forgot the date']
            save_assessment(session,row,item)
        save_assessment(session,rows[1],assessment('b'))
    monkeypatch.setattr(api,'get_engine',lambda:engine)
    client=TestClient(app)
    data=client.get('/api/data').json()
    status=data['research_status']
    assert status['state']=='completed'
    assert (status['analyzed_count'],status['retrieval_count'],status['unrelated_count'],status['incomplete_memory_count'])==(2,1,1,1)
    assert status['human_reviewed_count']==0
    assert data['themes']==[{'theme':'Poor or missing search matches','count':1}]
    cards=client.get('/api/insights').json()['insights']
    assert cards[0]['evidence_id']=='a' and cards[0]['review_count']==1
    evidence=client.get('/api/research/evidence?category=incomplete_memory').json()
    assert evidence['total']==1
    assert evidence['records'][0]['missing_details']==['forgot the date']
    assert client.get('/api/research/evidence?category=retrieval').json()['total']==0
    assert client.get('/api/research/evidence?offset=1').json()['records']==[]
    assert client.get('/api/research/evidence?category=bogus').status_code==422
    with get_session(engine) as session:
        row=session.get(ReviewMetadata,'a'); row.text='Changed source'; session.commit()
    status=client.get('/api/data').json()['research_status']
    assert status['state']=='partial' and status['pending_count']==1 and status['retrieval_count']==0


def test_running_and_failed_counts_reconcile(tmp_path,monkeypatch):
    import src.app.api as api
    engine=get_engine(tmp_path/'partial.db');init_db(engine)
    with get_session(engine) as session:
        rows=[ReviewMetadata(id=str(i),source='reddit',text='General review') for i in range(3)]
        session.add_all(rows);session.commit()
        save_assessment(session,rows[0],assessment('0'))
        save_assessment(session,rows[1],error='RateLimitError')
        session.add(ResearchRun(id='run',version=ANALYSIS_VERSION,status='running',started_at=utc_now(),updated_at=utc_now()));session.commit()
    monkeypatch.setattr(api,'get_engine',lambda:engine)
    status=TestClient(app).get('/api/data').json()['research_status']
    assert status['state']=='running'
    assert status['failed_other_count'] >= 0
    assert (status['analyzed_count'],status['failed_count'],status['pending_count'])==(1,1,1)
