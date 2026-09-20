import json

from src.process.catalog_runner import assess_batch, make_batches, run_catalog_analysis
from src.process.catalog_schema import CATALOG_VERSION
from src.process.db import (Phase1CatalogAssessment, Phase1CatalogRow,
                            get_engine, get_session, init_db)


class FakeLLM:
    def invoke(self, messages):
        payload = json.loads(messages[1][1])
        return {'assessments': [dict(
            row_id=item['row_id'], search_relevance='yes',
            issue_class='observed_retrieval_issue', target_media=['photo'],
            remembered_clues=[], forgotten_details=[], search_methods=['keyword'],
            observed_symptoms=['no_results'], journey_stages=['matching_or_coverage'],
            issue_quote='Search returned nothing.', remembered_quote=None,
            forgotten_quote=None, action_quote=None,
            result_quote='Search returned nothing.', confidence='high',
            summary='The search returned no photos.') for item in payload]}


def add_rows(engine, count):
    with get_session(engine) as session:
        for number in range(1, count + 1):
            session.add(Phase1CatalogRow(
                id=f'phase1_{number:05d}', row_number=number, source_file='test.csv',
                source_type='existing_in_scope_evidence', source='Community',
                url='https://example.org', text='Search returned nothing.', raw_json='{}',
                content_hash=f'hash-{number}', active=1, imported_at='now'))
        session.commit()


def test_runner_processes_all_rows_in_batches_and_skips_saved_results(tmp_path):
    engine = get_engine(tmp_path / 'catalog.db')
    init_db(engine)
    add_rows(engine, 5)
    with get_session(engine) as session:
        rows = session.query(Phase1CatalogRow).order_by(Phase1CatalogRow.row_number).all()
        assert [len(batch) for batch in make_batches(rows, max_items=2)] == [2, 2, 1]
    first = run_catalog_analysis(engine=engine, llm=FakeLLM(), workers=2, batch_size=2)
    assert first['scheduled'] == first['succeeded'] == 5
    assert first['failed'] == 0
    with get_session(engine) as session:
        assert session.query(Phase1CatalogAssessment).filter_by(
            version=CATALOG_VERSION, status='succeeded').count() == 5
    again = run_catalog_analysis(engine=engine, llm=FakeLLM(), workers=2, batch_size=2)
    assert again['scheduled'] == 0
    with get_session(engine) as session:
        saved = session.get(Phase1CatalogAssessment, ('phase1_00003', CATALOG_VERSION))
        saved.status = 'failed'
        saved.error = 'test_failure'
        session.commit()
    resumed = run_catalog_analysis(engine=engine, llm=FakeLLM(), workers=2, batch_size=2)
    assert resumed['scheduled'] == resumed['succeeded'] == 1
    engine.dispose()


def test_bad_batch_is_split_without_losing_other_rows(tmp_path):
    engine = get_engine(tmp_path / 'split.db')
    init_db(engine)
    add_rows(engine, 3)
    with get_session(engine) as session:
        rows = session.query(Phase1CatalogRow).order_by(Phase1CatalogRow.row_number).all()
        class SplitLLM(FakeLLM):
            def invoke(self, messages):
                if len(json.loads(messages[1][1])) > 1:
                    raise ValueError('Invalid batch shape')
                return super().invoke(messages)

        results = assess_batch(rows, SplitLLM(), pause=lambda _: None)
        assert len(results) == 3
        assert all(result is not None and error is None for _, result, error in results)
    engine.dispose()
