from src.process.db import ReviewMetadata, get_engine, get_session, init_db
from src.process.issue_chat import answer_issue_question
from src.process.issue_store import save_issue
from tests.process.test_issue_runner import issue


def test_chat_uses_only_current_source_backed_issue_decisions(tmp_path):
    engine = get_engine(tmp_path / 'chat.db')
    init_db(engine)
    with get_session(engine) as session:
        problem = ReviewMetadata(id='issue', source='reddit',
                                 text='I searched for my dog photos and got only food pictures.',
                                 url='https://reddit.com/r/googlephotos/comments/issue')
        praise = ReviewMetadata(id='praise', source='play_store', text='Dog Memories makes beautiful videos.')
        session.add_all([problem, praise])
        session.commit()
        save_issue(session, problem, issue('issue', disposition='retrieval_issue',
                                           issue_quote='got only food pictures', photo_target='my dog photos',
                                           attempted_action='searched for my dog photos',
                                           observed_result='got only food pictures', failure_stage='poor_matches'))
        save_issue(session, praise, issue('praise', disposition='context', rationale='Praise.'))
        answer = answer_issue_question(session, 'What goes wrong when searching for dog photos?')
        assert len(answer['sources']) == 1
        assert answer['sources'][0]['id'] == 'issue'
        assert 'got only food pictures' in answer['answer']
        assert 'beautiful videos' not in answer['answer']
        unrelated = answer_issue_question(session, 'What problems exist with payments?')
        assert unrelated['sources'] == []
    engine.dispose()


def test_chat_summarizes_major_reasons_with_distinct_source_examples(tmp_path):
    engine = get_engine(tmp_path / 'reasons.db')
    init_db(engine)
    with get_session(engine) as session:
        rows = [
            ReviewMetadata(id='missing', source='reddit',
                           text='I searched for my dog photos and got only food pictures.',
                           url='https://reddit.com/r/googlephotos/comments/missing'),
            ReviewMetadata(id='faces', source='play_store',
                           text='I searched for my daughter and the face group showed a stranger.',
                           url='https://play.google.com/store/apps/details?id=com.google.android.apps.photos&reviewId=1'),
            ReviewMetadata(id='praise', source='play_store', text='Search is great.'),
            ReviewMetadata(id='pending', source='reddit', text='I cannot find my old photo.'),
        ]
        session.add_all(rows)
        session.commit()
        save_issue(session, rows[0], issue('missing', disposition='retrieval_issue',
                                           issue_quote='got only food pictures',
                                           photo_target='my dog photos',
                                           attempted_action='searched for my dog photos',
                                           observed_result='got only food pictures',
                                           failure_stage='poor_matches'))
        save_issue(session, rows[1], issue('faces', disposition='retrieval_issue',
                                           issue_quote='the face group showed a stranger',
                                           photo_target='my daughter',
                                           attempted_action='searched for my daughter',
                                           observed_result='the face group showed a stranger',
                                           failure_stage='face_group'))
        save_issue(session, rows[2], issue('praise', disposition='context'))
        answer = answer_issue_question(
            session, 'Why are people facing retrieval-related information problems? What are all the major reasons?')
        assert 'Poor or missing search matches' in answer['answer']
        assert 'Incorrect person grouping' in answer['answer']
        assert '2 of 3 AI-screened' in answer['answer']
        assert 'Assessment remaining: 1 pending and 0 failed' in answer['answer']
        assert 'internal technical causes' in answer['answer']
        assert {source['id'] for source in answer['sources']} == {'missing', 'faces'}
        assert 'Search is great' not in answer['answer']
    engine.dispose()
