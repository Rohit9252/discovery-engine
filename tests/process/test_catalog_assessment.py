import json
from types import SimpleNamespace

import pytest

from src.process.catalog_extract import extract_catalog_batch
from src.process.catalog_schema import CatalogAssessment, validate_catalog_assessment
from src.process.catalog_store import current_catalog_assessments, save_catalog_assessment
from src.process.db import get_engine, get_session, init_db


def catalog_row(row_id, text, source_type='existing_in_scope_evidence', content_hash='hash-a'):
    return SimpleNamespace(id=row_id, text=text, source_type=source_type, source='Community',
                           url='https://example.org/thread/1', raw_json=json.dumps({}),
                           content_hash=content_hash)


def assessment(row_id, issue_class='observed_retrieval_issue', **overrides):
    values = dict(row_id=row_id, search_relevance='yes', issue_class=issue_class,
                  target_media=['photo'], remembered_clues=[], forgotten_details=[],
                  search_methods=['keyword'], observed_symptoms=['no_results'],
                  journey_stages=['matching_or_coverage'], issue_quote='Search returned nothing.',
                  remembered_quote=None, forgotten_quote=None, action_quote=None,
                  result_quote='Search returned nothing.', confidence='high',
                  summary='The search returned no photos.')
    values.update(overrides)
    return CatalogAssessment(**values)


def test_multi_tag_issue_and_explicit_memory_boundary():
    row = catalog_row('phase1_00001', 'I remember my dog at the beach, but forget when we went. '
                      'Search returned nothing.')
    result = assessment(row.id, issue_class='direct_memory_issue',
                        remembered_clues=['pet', 'place'], forgotten_details=['date'],
                        remembered_quote='I remember my dog at the beach',
                        forgotten_quote='forget when we went')
    assert validate_catalog_assessment(result, row).remembered_clues == ['pet', 'place']

    missing_memory = assessment(row.id, issue_class='direct_memory_issue',
                                remembered_clues=['pet'], forgotten_details=['date'],
                                remembered_quote='I remember my dog at the beach')
    assert validate_catalog_assessment(missing_memory, row).issue_class == 'observed_retrieval_issue'


def test_praise_request_and_scenario_cannot_be_reported_issues():
    praise = catalog_row('phase1_00002', 'Search works brilliantly.')
    positive = assessment(praise.id, issue_class='retrieval_success',
                          issue_quote=None, result_quote=None)
    assert validate_catalog_assessment(positive, praise).observed_symptoms == []
    request = catalog_row('phase1_00003', 'Please add a search filter.')
    requested = validate_catalog_assessment(assessment(request.id, issue_class='search_request',
                                                       issue_quote=None, result_quote=None), request)
    assert requested.observed_symptoms == []
    scenario = catalog_row('phase1_00004', 'Scenario: find a dog photo; zero results.',
                           source_type='web_grounded_scenario')
    assert validate_catalog_assessment(assessment(scenario.id), scenario).issue_class == 'scenario'
    valid = assessment(scenario.id, issue_class='scenario', issue_quote=None,
                       result_quote=None, confidence='medium')
    assert validate_catalog_assessment(valid, scenario).issue_class == 'scenario'


def test_paraphrased_issue_quote_falls_back_to_exact_original_text():
    row = catalog_row('phase1_00006', 'Only two photos appeared instead of hundreds.')
    result = assessment(row.id, issue_quote='Results were limited.',
                        result_quote='Results were limited.',
                        observed_symptoms=['missing_expected_items'])
    checked = validate_catalog_assessment(result, row)
    assert checked.issue_quote == checked.result_quote == row.text


def test_cannot_find_is_not_a_forgotten_target_detail():
    row = catalog_row('phase1_00007', 'I remember my dog at the beach. I cannot find the photo anywhere. '
                      'Search returned nothing.')
    result = assessment(row.id, issue_class='direct_memory_issue',
                        remembered_clues=['pet', 'place'], forgotten_details=['date'],
                        remembered_quote='I remember my dog at the beach',
                        forgotten_quote='I cannot find the photo anywhere.')
    checked = validate_catalog_assessment(result, row)
    assert checked.issue_class == 'observed_retrieval_issue'
    assert checked.forgotten_details == []


def test_batch_identity_and_content_hash_cache(tmp_path):
    row = catalog_row('phase1_00005', 'Search returned nothing.')
    class FakeLLM:
        def invoke(self, messages):
            return {'assessments': [assessment(row.id).model_dump()]}

    result = extract_catalog_batch([row], FakeLLM())[0]
    engine = get_engine(tmp_path / 'test.db')
    init_db(engine)
    with get_session(engine) as session:
        save_catalog_assessment(session, row, result)
        assert current_catalog_assessments(session, [row])[row.id].status == 'succeeded'
        changed = catalog_row(row.id, row.text, content_hash='hash-b')
        assert current_catalog_assessments(session, [changed]) == {}
    engine.dispose()
