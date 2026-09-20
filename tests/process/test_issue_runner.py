from types import SimpleNamespace

import pytest

from src.process.db import ReviewMetadata, ResearchAnalysis, get_engine, get_session, init_db
from src.process.issue_schema import IssueAssessment
from src.process.issue_store import current_issue_analysis, save_issue
from src.process.issue_runner import candidate_ids, run_issue_analysis
from src.process.research_store import save_assessment
from tests.process.test_research import assessment


def issue(review_id, **changes):
    values = dict(review_id=review_id, disposition='unrelated', source_type='first_person',
                  rationale='No photo retrieval problem.', issue_quote=None, photo_target=None,
                  remembered_clue=None, missing_detail=None, attempted_action=None,
                  observed_result=None, workaround=None, failure_stage='unknown')
    values.update(changes)
    return IssueAssessment(**values)


@pytest.fixture
def engine(tmp_path):
    engine = get_engine(tmp_path / 'issue.db')
    init_db(engine)
    with get_session(engine) as session:
        session.add_all([
            ReviewMetadata(id='a', source='reddit', text='I searched for my dog photos and got only food pictures.',
                           url='https://reddit.com/r/googlephotos/comments/a'),
            ReviewMetadata(id='b', source='play_store', text='Memories makes beautiful videos.'),
            ReviewMetadata(id='c', source='play_store', text='Search failed for my cat.'),
        ])
        session.commit()
        save_assessment(session, session.get(ReviewMetadata, 'a'), assessment(
            'a', relevance='retrieval', evidence_quotes=['got only food pictures'], outcome='failure'))
        save_assessment(session, session.get(ReviewMetadata, 'b'), assessment('b'))
        save_assessment(session, session.get(ReviewMetadata, 'c'), error='provider_rate_limit')
    yield engine
    engine.dispose()


def test_priority_uses_prior_positives_and_failures_and_samples_negatives(engine):
    with get_session(engine) as session:
        rows = session.query(ReviewMetadata).order_by(ReviewMetadata.id).all()
        assert candidate_ids(session, rows, 'priority') == {'a', 'c'}
        assert candidate_ids(session, rows, 'negative_sample') == {'b'}


def test_issue_runner_checkpoints_skips_success_and_keeps_old_labels(engine):
    class Fake:
        def invoke(self, messages):
            import json
            record = json.loads(messages[1][1])
            if record['review_id'] == 'a':
                return issue('a', disposition='retrieval_issue',
                             issue_quote='got only food pictures', photo_target='my dog photos',
                             attempted_action='searched for my dog photos',
                             observed_result='got only food pictures', failure_stage='poor_matches')
            return issue('c', disposition='retrieval_issue', issue_quote='Search failed',
                         photo_target='my cat', attempted_action='Search', observed_result='Search failed')

    first = run_issue_analysis(engine=engine, llm=Fake(), workers=2, scope='priority')
    assert first['scheduled'] == 2 and first['succeeded'] == 2
    assert run_issue_analysis(engine=engine, llm=Fake(), scope='priority')['scheduled'] == 0
    with get_session(engine) as session:
        rows = session.query(ReviewMetadata).all()
        assert set(current_issue_analysis(session, rows)) == {'a', 'c'}
        assert session.query(ResearchAnalysis).count() == 3
        row = session.get(ReviewMetadata, 'a')
        row.text = 'Changed source.'
        session.commit()
        assert 'a' not in current_issue_analysis(session, rows)


def test_failed_issue_output_is_not_saved_as_unrelated(engine):
    class Broken:
        def invoke(self, messages):
            raise RuntimeError('provider unavailable')
    result = run_issue_analysis(engine=engine, llm=Broken(), workers=1, scope='priority', limit=1)
    assert result['failed'] == 1
    with get_session(engine) as session:
        row = session.query(ReviewMetadata).filter_by(id='a').one()
        saved = current_issue_analysis(session, [row])['a']
        assert saved.status == 'failed' and saved.result_json is None


def test_nonissue_result_is_persisted_without_issue_fields(engine):
    with get_session(engine) as session:
        row = session.get(ReviewMetadata, 'b')
        save_issue(session, row, issue('b', disposition='context', rationale='Praise for automatic Memories.'))
        saved = current_issue_analysis(session, [row])['b']
        assert saved.status == 'succeeded'
        assert IssueAssessment.model_validate_json(saved.result_json).issue_quote is None
