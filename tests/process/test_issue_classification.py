import pytest

from src.process.issue_schema import IssueAssessment, validate_issue


def decision(review_id='r1', **changes):
    values = dict(
        review_id=review_id, disposition='unrelated', source_type='first_person',
        rationale='No retrieval problem.', issue_quote=None, photo_target=None,
        remembered_clue=None, missing_detail=None, attempted_action=None,
        observed_result=None, workaround=None, failure_stage='unknown',
    )
    values.update(changes)
    return IssueAssessment(**values)


def test_direct_partial_memory_issue_requires_literal_clues_gap_and_failure():
    text = 'I remember a red car photo but forgot when it was taken. Searching red car finds nothing.'
    result = decision(
        disposition='direct_memory_issue', issue_quote='Searching red car finds nothing',
        photo_target='a red car photo', remembered_clue='red car',
        missing_detail='forgot when it was taken', attempted_action='Searching red car',
        observed_result='finds nothing', failure_stage='poor_matches',
    )
    assert validate_issue(result, text) == result
    with pytest.raises(ValueError, match='memory'):
        validate_issue(result.model_copy(update={'missing_detail': None}), text)
    with pytest.raises(ValueError, match='source span'):
        validate_issue(result.model_copy(update={'issue_quote': 'search failed for my car'}), text)


def test_observed_retrieval_issue_does_not_invent_missing_memory():
    text = 'I searched for my dog photos and got only food pictures.'
    result = decision(
        disposition='retrieval_issue', issue_quote='got only food pictures',
        photo_target='my dog photos', attempted_action='searched for my dog photos',
        observed_result='got only food pictures', failure_stage='poor_matches',
    )
    assert validate_issue(result, text).missing_detail is None
    with pytest.raises(ValueError, match='observed'):
        validate_issue(result.model_copy(update={'observed_result': None}), text)


def test_praise_and_feature_wishes_cannot_carry_issue_fields():
    for text in ('Memories makes beautiful videos.', 'I wish albums could be sorted by date.'):
        assert validate_issue(decision(disposition='context'), text).issue_quote is None
        with pytest.raises(ValueError, match='Non-issue'):
            validate_issue(decision(disposition='context', issue_quote=text), text)


def test_secondary_advice_and_unclear_authorship_cannot_be_issues():
    text = 'Try searching by date if you cannot find it.'
    with pytest.raises(ValueError, match='first-person'):
        validate_issue(decision(disposition='retrieval_issue', source_type='secondary_or_advice',
                                issue_quote='cannot find it', observed_result='cannot find it'), text)
    assert validate_issue(decision(disposition='insufficient_context', source_type='unclear'), text)


def test_issue_must_name_retrieval_barrier_even_if_it_mentions_a_photo():
    text = 'I love seeing my old photos in Memories.'
    with pytest.raises(ValueError, match='observed'):
        validate_issue(decision(disposition='retrieval_issue', issue_quote='old photos'), text)


def test_issue_quote_must_itself_contain_the_bad_result():
    text = 'I tried search yesterday. It returned unrelated photos.'
    with pytest.raises(ValueError, match='bad result'):
        validate_issue(decision(disposition='retrieval_issue', issue_quote='I tried search yesterday',
                                photo_target='photos', observed_result='returned unrelated photos'), text)
