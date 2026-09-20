from types import SimpleNamespace

import pytest

from src.process.db import ReviewMetadata, ResearchAnalysis, ResearchRun, get_engine, get_session, init_db
from src.process.research_schema import RetrievalAssessment, AssessmentBatch, validate_assessment
from src.process.research_store import save_assessment, current_analysis
from src.process.research_extract import extract_batch
from src.process.research_runner import run_research, make_batches


def assessment(review_id='a', **kwargs):
    values = dict(review_id=review_id, relevance='unrelated', rationale='General feedback.', evidence_quotes=[],
                  remembered_clues=[], missing_details=[], attempted_queries=[], workarounds=[],
                  outcome='not_reported', failure_mechanism='not_reported', failure_evidence=None)
    values.update(kwargs)
    return RetrievalAssessment(**values)


@pytest.fixture
def engine(tmp_path):
    engine = get_engine(tmp_path / 'research.db')
    init_db(engine)
    with get_session(engine) as session:
        session.add_all([ReviewMetadata(id='a', source='reddit', text='Search cannot find my dog.'),
                         ReviewMetadata(id='b', source='play_store', text='Great backup app.')])
        session.commit()
    yield engine
    engine.dispose()


def test_fabricated_quote_and_inferred_memory_are_rejected():
    with pytest.raises(ValueError, match='exact'):
        validate_assessment(assessment(relevance='retrieval', evidence_quotes=['invented']), 'Search failed.')
    with pytest.raises(ValueError, match='Incomplete memory'):
        validate_assessment(assessment(relevance='incomplete_memory', evidence_quotes=['Search failed.']), 'Search failed.')
    with pytest.raises(ValueError, match='Unrelated'):
        validate_assessment(assessment(outcome='failure'), 'Backup failed.')
    with pytest.raises(ValueError, match='stated year'):
        validate_assessment(assessment(relevance='incomplete_memory', evidence_quotes=['my photo 2016'], remembered_clues=['my photo'], missing_details=['2016']), 'my photo 2016')


def test_literal_memory_evidence_is_accepted():
    text = 'I remember a red car but forgot the date. I searched red car and found nothing.'
    item = assessment(relevance='incomplete_memory', evidence_quotes=['forgot the date'], remembered_clues=['a red car'],
                      missing_details=['forgot the date'], attempted_queries=['searched red car'], outcome='failure',
                      failure_mechanism='poor_matches', failure_evidence='found nothing')
    assert validate_assessment(item, text) == item


def test_whitespace_alignment_retains_exact_original_source_and_rejects_changed_words():
    item=assessment(relevance='retrieval',evidence_quotes=['Search finds nothing'])
    assert validate_assessment(item,'Search\n finds\t nothing').evidence_quotes==['Search\n finds\t nothing']
    with pytest.raises(ValueError,match='exact'):
        validate_assessment(assessment(relevance='retrieval',evidence_quotes=['Search returned nothing']),'Search finds nothing')


def test_transport_schema_cannot_assign_retrieval_fields_to_unrelated_feedback():
    from src.process.research_schema import TransportBatch
    from src.process.research_extract import ResearchStructuredLLM
    payload={'assessments':[{'review_id':'a','relevance':'unrelated','rationale':'Backup praise.'}]}
    batch=TransportBatch.model_validate(payload)
    fake=SimpleNamespace(invoke=lambda messages:batch)
    result=ResearchStructuredLLM(fake).invoke([]).assessments[0]
    assert result.outcome=='not_reported' and result.evidence_quotes==[]
    payload['assessments'][0]['outcome']='success'
    with pytest.raises(ValueError):TransportBatch.model_validate(payload)


def test_source_change_invalidates_saved_result_and_writes_are_idempotent(engine):
    with get_session(engine) as session:
        row = session.get(ReviewMetadata, 'a')
        save_assessment(session, row, assessment())
        save_assessment(session, row, assessment())
        assert session.query(ResearchAnalysis).count() == 1
        assert 'a' in current_analysis(session, [row])
        row.text = 'Source changed.'
        session.commit()
        assert current_analysis(session, [row]) == {}


def test_wrong_identity_is_not_saved(engine):
    with get_session(engine) as session:
        with pytest.raises(ValueError, match='identity'):
            save_assessment(session, session.get(ReviewMetadata, 'a'), assessment('b'))
        assert session.query(ResearchAnalysis).count() == 0


def test_batch_missing_or_duplicate_ids_are_retried_and_fail():
    class Fake:
        calls = 0
        def invoke(self, messages):
            self.calls += 1
            return AssessmentBatch(assessments=[assessment('a'), assessment('a')])
    fake = Fake()
    with pytest.raises(ValueError, match='IDs'):
        extract_batch([SimpleNamespace(id='a', source='reddit', text='Good app.')], fake, sleep=lambda _: None)
    assert fake.calls == 3


def test_bounded_batches_preserve_all_records():
    rows = [SimpleNamespace(id=str(i), text='123456') for i in range(5)]
    batches = list(make_batches(rows, size=3, char_limit=10))
    assert [r.id for batch in batches for r in batch] == [str(i) for i in range(5)]
    assert len(batches) == 5


def test_one_invalid_item_does_not_discard_other_valid_assessments():
    from src.process.research_extract import BatchValidationError
    class Fake:
        def invoke(self, messages):
            return AssessmentBatch(assessments=[assessment('a'),assessment('b',relevance='retrieval',evidence_quotes=['invented'])])
    rows=[SimpleNamespace(id=key,source='reddit',text='Good app.') for key in ('a','b')]
    with pytest.raises(BatchValidationError) as caught:
        extract_batch(rows,Fake(),sleep=lambda _:None)
    assert set(caught.value.partial_results)=={'a'}
    assert set(caught.value.errors)=={'b'}


def test_runner_saves_partial_batch_results_independently(engine):
    class Fake:
        def invoke(self,messages):
            return AssessmentBatch(assessments=[assessment('a'),assessment('b',relevance='retrieval',evidence_quotes=['invented'])])
    report=run_research(engine=engine,llm=Fake())
    assert report['succeeded']==1 and report['failed']==1
    with get_session(engine) as session:
        rows=current_analysis(session,session.query(ReviewMetadata).all())
        assert rows['a'].status=='succeeded' and rows['a'].error is None
        assert rows['b'].status=='failed' and rows['b'].result_json is None
        assert rows['b'].error == 'validation_source_quote_mismatch'


def test_runner_checkpoints_and_resumes_without_reprocessing(engine):
    class Fake:
        calls = 0
        def invoke(self, messages):
            import json
            self.calls += 1
            return AssessmentBatch(assessments=[assessment(row['review_id']) for row in json.loads(messages[1][1])])
    fake = Fake()
    assert run_research(engine=engine, llm=fake)['succeeded'] == 2
    assert run_research(engine=engine, llm=fake)['scheduled'] == 0
    assert fake.calls == 1
    with get_session(engine) as session:
        assert session.query(ReviewMetadata).count() == 2
        assert {row.status for row in session.query(ResearchRun)} == {'completed'}
        from src.process.db import ResearchRunProgress
        assert sorted(row.completed for row in session.query(ResearchRunProgress))==[0,2]


def test_failed_provider_is_saved_as_failure_not_unrelated(engine):
    class Fake:
        def invoke(self, messages):
            raise ValueError('broken output')
    assert run_research(engine=engine, llm=Fake())['failed'] == 2
    with get_session(engine) as session:
        assert {row.status for row in session.query(ResearchAnalysis)} == {'failed'}
        assert all(row.result_json is None for row in session.query(ResearchAnalysis))
        assert session.query(ResearchRun).one().status == 'completed_with_errors'


def test_first_pass_can_leave_failed_records_for_later_pipeline(engine):
    class Fake:
        def invoke(self, messages):
            import json
            items = json.loads(messages[1][1])
            return AssessmentBatch(assessments=[assessment(row['review_id']) for row in items])
    with get_session(engine) as session:
        save_assessment(session, session.get(ReviewMetadata, 'a'), error='provider_rate_limit')
    report = run_research(engine=engine, llm=Fake(), retry_failed=False)
    assert report['scheduled'] == 1 and report['succeeded'] == 1
    with get_session(engine) as session:
        assert session.query(ResearchAnalysis).filter_by(review_id='a').one().status == 'failed'


def test_concurrent_run_is_rejected(engine):
    from src.process.research_schema import ANALYSIS_VERSION
    from src.process.research_store import utc_now
    with get_session(engine) as session:
        session.add(ResearchRun(id='live',version=ANALYSIS_VERSION,status='running',started_at=utc_now(),updated_at=utc_now()))
        session.commit()
    with pytest.raises(RuntimeError, match='already active'):
        run_research(engine=engine, llm=object())


def test_semantic_review_rechecks_positives_and_possible_false_negatives(engine):
    from src.process.research_runner import needs_semantic_review, REVIEW_MODEL
    with get_session(engine) as session:
        row=session.get(ReviewMetadata,'a')
        save_assessment(session,row,assessment())
        saved=current_analysis(session,[row])['a']
        assert needs_semantic_review(row,saved)  # search-language negative
        save_assessment(session,row,assessment(),model=REVIEW_MODEL)
        assert not needs_semantic_review(row,current_analysis(session,[row])['a'])
        general=session.get(ReviewMetadata,'b')
        save_assessment(session,general,assessment('b'))
        assert not needs_semantic_review(general,current_analysis(session,[general])['b'])


def test_report_reconciles_evidence_and_excludes_unrelated_records(engine):
    from src.process.research_report import build_report
    with get_session(engine) as session:
        rows=session.query(ReviewMetadata).order_by('id').all()
        save_assessment(session,rows[0],assessment(relevance='retrieval',evidence_quotes=['Search cannot find my dog.'],outcome='failure',failure_mechanism='poor_matches',failure_evidence='cannot find my dog'))
        save_assessment(session,rows[1],assessment('b'))
        report=build_report(session,rows)
        assert report['status']['analyzed_count']==2
        assert report['relevance_counts']=={'retrieval':1,'unrelated':1}
        assert report['retrieval_by_source']=={'reddit':1}
        assert [row['review_id'] for row in report['evidence']]==['a']
        assert sum(row['count'] for row in report['mechanisms'])==report['status']['known_mechanism_count']


def test_unexplained_failure_and_retrieval_need_do_not_become_mechanisms(engine):
    from src.process.research_report import build_report
    with get_session(engine) as session:
        first = session.get(ReviewMetadata, 'a')
        second = session.get(ReviewMetadata, 'b')
        save_assessment(session, first, assessment(
            relevance='retrieval', evidence_quotes=['Search cannot find my dog.'],
            outcome='failure', failure_mechanism='not_reported'))
        second.text = 'I want to search my albums by name.'
        session.commit()
        save_assessment(session, second, assessment(
            review_id='b', relevance='retrieval', evidence_quotes=['search my albums by name'],
            outcome='not_reported', failure_mechanism='not_reported'))
        report = build_report(session, [first, second])
        assert report['mechanisms'] == []
        assert report['status']['unclear_failure_count'] == 1
        assert report['status']['no_reported_failure_count'] == 1
        assert {row['label'] for row in report['other_retrieval_evidence']} == {
            'Reported failure, cause unclear', 'Retrieval need, outcome not stated'}
