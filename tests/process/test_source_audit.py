from types import SimpleNamespace
from unittest.mock import MagicMock
from src.process.db import get_engine, init_db, get_session, ReviewMetadata, ReviewExclusion
from src.process.source_audit import active_reviews


def test_exclusion_preserves_original_record(tmp_path):
    engine = get_engine(tmp_path / 'test.db')
    init_db(engine)
    with get_session(engine) as session:
        session.add_all([ReviewMetadata(id='a',source='reddit',text='Google Photos search'),ReviewMetadata(id='b',source='reddit',text='Pixel Bluetooth toggle')])
        session.add(ReviewExclusion(review_id='b',reason='Unconfirmed product context'))
        session.commit()
        assert session.query(ReviewMetadata).count() == 2
        assert [row.id for row in active_reviews(session)] == ['a']
        session.query(ReviewExclusion).filter_by(review_id='b').delete()
        session.commit()
        assert active_reviews(session).count() == 2


def test_index_feedback_upserts_stable_ids_without_ai_labels():
    from src.process.index_feedback import index_rows
    collection = MagicMock()
    rows = [SimpleNamespace(id='a',text='Search is broken',source='reddit',url=None,author=None)]
    index_rows(collection,rows)
    collection.upsert.assert_called_once()
    assert collection.upsert.call_args.kwargs['ids'] == ['a']
    assert collection.upsert.call_args.kwargs['metadatas'][0]['analysis_status'] == 'raw_feedback'
