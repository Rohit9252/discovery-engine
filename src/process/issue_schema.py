"""Source-grounded issue decisions for assignment Part One."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.process.research_schema import canonical_source_span


ISSUE_VERSION = 'issue-v3'
ISSUE_MODEL = 'gpt-4o-mini'
ISSUE_DISPOSITIONS = {'direct_memory_issue', 'retrieval_issue'}


class IssueAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid')

    review_id: str
    disposition: Literal['direct_memory_issue', 'retrieval_issue', 'context', 'unrelated', 'insufficient_context']
    source_type: Literal['first_person', 'direct_user_quote', 'secondary_or_advice', 'unclear']
    rationale: str = Field(description='One concise sentence stating what the source does or does not report.')
    issue_quote: str | None = Field(description='Exact source span reporting the retrieval barrier, or null.')
    photo_target: str | None = Field(description='Exact span identifying the existing photo or set the person sought, or null.')
    remembered_clue: str | None = Field(description='Exact span of a clue recalled about that target, or null.')
    missing_detail: str | None = Field(description='Exact span where the author says a target detail is unknown or forgotten, or null.')
    attempted_action: str | None = Field(description='Exact span of a search, browsing, or refinement actually attempted, or null.')
    observed_result: str | None = Field(description='Exact span of the reported unsuccessful retrieval outcome, or null.')
    workaround: str | None = Field(description='Exact span of a workaround actually used, or null.')
    failure_stage: Literal['poor_matches', 'metadata_or_index', 'face_group', 'navigation',
                           'query_formulation', 'search_unavailable', 'ai_assistant', 'other', 'unknown']


def validate_issue(result: IssueAssessment, source_text: str) -> IssueAssessment:
    """Enforce literal evidence and the strongest mechanical issue boundaries."""
    for field in ('issue_quote', 'photo_target', 'remembered_clue', 'missing_detail',
                  'attempted_action', 'observed_result', 'workaround'):
        span = getattr(result, field)
        if span is None:
            continue
        aligned = canonical_source_span(span, source_text)
        if aligned is None:
            raise ValueError(f'{result.review_id}: {field} must be an exact source span')
        setattr(result, field, aligned)

    is_issue = result.disposition in ISSUE_DISPOSITIONS
    if is_issue:
        if result.source_type not in {'first_person', 'direct_user_quote'}:
            raise ValueError('Issue decisions require a first-person report or direct user quote')
        if not result.issue_quote or not result.observed_result:
            raise ValueError('Issue decisions require an observed retrieval barrier and issue quote')
        if result.observed_result not in result.issue_quote:
            raise ValueError('Issue quote must itself contain the observed bad result')
        if not result.photo_target and not result.attempted_action:
            raise ValueError('Issue decisions require a target or an attempted retrieval action')
        if result.disposition == 'direct_memory_issue' and not (
                result.photo_target and result.remembered_clue and result.missing_detail):
            raise ValueError('Direct memory issues require target, remembered clue, and explicit missing memory')
    else:
        if any(getattr(result, field) is not None for field in (
                'issue_quote', 'photo_target', 'remembered_clue', 'missing_detail',
                'attempted_action', 'observed_result', 'workaround')) or result.failure_stage != 'unknown':
            raise ValueError('Non-issue decisions cannot contain issue evidence fields')
    return result
