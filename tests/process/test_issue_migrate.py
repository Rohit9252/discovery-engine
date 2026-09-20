from src.process.db import ReviewMetadata, get_engine, get_session, init_db
from src.process.issue_migrate import transfer_exact_decisions
from src.process.issue_store import current_issue_analysis, save_issue
from tests.process.test_issue_runner import issue


def test_only_exact_source_records_reuse_successful_decisions(tmp_path):
    old_path = tmp_path / 'old.db'
    old_engine = get_engine(old_path)
    new_engine = get_engine(tmp_path / 'new.db')
    init_db(old_engine)
    init_db(new_engine)
    text = 'I searched for my dog photos and got only food pictures.'
    url = 'https://reddit.com/r/googlephotos/comments/source'
    with get_session(old_engine) as session:
        source = ReviewMetadata(id='old', source='reddit', text=text, url=url)
        session.add(source)
        session.commit()
        save_issue(session, source, issue('old', disposition='retrieval_issue',
                                          issue_quote='got only food pictures',
                                          photo_target='my dog photos',
                                          attempted_action='searched for my dog photos',
                                          observed_result='got only food pictures'))
    with get_session(new_engine) as session:
        session.add_all([
            ReviewMetadata(id='new', source='reddit', text=text, url=url),
            ReviewMetadata(id='different-url', source='reddit', text=text,
                           url='https://reddit.com/r/googlephotos/comments/other'),
        ])
        session.commit()
    assert transfer_exact_decisions(old_path, new_engine) == {'reused': 1, 'not_reusable': 1}
    assert transfer_exact_decisions(old_path, new_engine) == {'already_present': 1, 'not_reusable': 1}
    with get_session(new_engine) as session:
        reviews = session.query(ReviewMetadata).all()
        saved = current_issue_analysis(session, reviews)
        assert set(saved) == {'new'}
        assert '"review_id":"new"' in saved['new'].result_json
    old_engine.dispose()
    new_engine.dispose()
