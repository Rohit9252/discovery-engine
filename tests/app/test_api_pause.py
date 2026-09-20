import pytest
from fastapi.testclient import TestClient

from src.process.db import ReviewMetadata, get_engine, get_session, init_db


def test_user_pause_blocks_paid_calls_and_preserves_read_only_dashboard(tmp_path, monkeypatch):
    import src.app.api as api
    import src.process.paths as paths
    import src.process.research_dashboard as dashboard
    from src.process.research_extract import get_research_llm
    flag=tmp_path/'api-paused.json';flag.write_text('{"paused":true}')
    for module in (api,paths,dashboard):monkeypatch.setattr(module,'API_PAUSE_FILE',flag)
    with pytest.raises(RuntimeError,match='paused'):get_research_llm()
    client=TestClient(api.app)
    response=client.post('/api/chat',json={'question':'Analyze retrieval'})
    assert response.status_code==503 and 'paused' in response.json()['error']
    engine=get_engine(tmp_path/'reviews.db');init_db(engine)
    with get_session(engine) as session:
        session.add(ReviewMetadata(id='a',source='reddit',text='Search cannot find my dog.'));session.commit()
    monkeypatch.setattr(api,'get_engine',lambda:engine)
    data=client.get('/api/data').json()
    assert data['research_status']['state']=='paused' and data['total_reviews']==1
