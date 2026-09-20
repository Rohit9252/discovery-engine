"""Typed, assignment-focused tags for each Phase 1 catalog row."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.process.research_schema import canonical_source_span


CATALOG_VERSION = 'phase1-catalog-v4'
CATALOG_MODEL = 'gpt-4o-mini'

EXPLICIT_MEMORY_GAP = re.compile(
    r"\b(?:don['’]?t|do not|can['’]?t|cannot|couldn['’]?t|could not)\s+"
    r"(?:quite\s+)?(?:remember|recall)\b|"
    r"\b(?:forgot|forgotten|forget)\b|"
    r"\b(?:not sure|no idea|unsure)\s+(?:of\s+)?(?:when|where|which|what)\b",
    re.IGNORECASE,
)


class CatalogAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid')

    row_id: str
    search_relevance: Literal['yes', 'no', 'unclear']
    issue_class: Literal['direct_memory_issue', 'observed_retrieval_issue',
                         'search_request', 'retrieval_success', 'related_context',
                         'unrelated', 'unclear', 'scenario']
    target_media: list[Literal['photo', 'video', 'screenshot', 'document', 'album']]
    remembered_clues: list[Literal['person', 'pet', 'place', 'event', 'approximate_time',
                                   'object_or_scene', 'visible_text', 'personal_context']]
    forgotten_details: list[Literal['date', 'place', 'album', 'exact_words', 'person', 'other']]
    search_methods: list[Literal['keyword', 'person_or_face', 'place', 'date', 'album',
                                 'natural_language', 'browse_or_scroll', 'ask_photos']]
    observed_symptoms: list[Literal['no_results', 'missing_expected_items', 'wrong_results',
                                    'difficult_to_evaluate', 'cannot_refine', 'face_grouping',
                                    'wrong_date_or_place', 'navigation', 'search_unavailable',
                                    'slow_or_error', 'other']]
    journey_stages: list[Literal['expressing_memory', 'matching_or_coverage',
                                 'evaluating_results', 'refining_query', 'browsing_navigation']]
    issue_quote: str | None = Field(description='Exact text reporting an observed retrieval problem, or null.')
    remembered_quote: str | None = Field(description='Exact text stating a remembered clue, or null.')
    forgotten_quote: str | None = Field(description='Exact text explicitly stating forgotten target information, or null.')
    action_quote: str | None = Field(description='Exact text stating a search or browse action actually attempted, or null.')
    result_quote: str | None = Field(description='Exact text stating the observed result, or null.')
    confidence: Literal['low', 'medium', 'high']
    summary: str = Field(description='One plain sentence explaining this row without inventing causes.')


class CatalogBatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessments: list[CatalogAssessment]


def validate_catalog_assessment(result: CatalogAssessment, row) -> CatalogAssessment:
    """Align evidence locally and protect the direct partial-memory boundary."""
    if result.row_id != row.id:
        raise ValueError('Catalog assessment row ID does not match input')
    scenario = row.source_type == 'web_grounded_scenario'
    if scenario:
        result.issue_class = 'scenario'
    elif result.issue_class == 'scenario':
        result.issue_class = 'unclear'
    for field in ('issue_quote', 'remembered_quote', 'forgotten_quote',
                  'action_quote', 'result_quote'):
        span = getattr(result, field)
        if span is None:
            continue
        aligned = canonical_source_span(span, row.text)
        setattr(result, field, aligned)
    if result.forgotten_details and not result.forgotten_quote:
        result.forgotten_details = []
    if result.forgotten_quote and not EXPLICIT_MEMORY_GAP.search(result.forgotten_quote):
        result.forgotten_quote = None
        result.forgotten_details = []
    if result.issue_class == 'direct_memory_issue' and not (
            result.remembered_quote and result.forgotten_quote and
            result.remembered_clues and result.forgotten_details):
        result.issue_class = 'observed_retrieval_issue'
        result.forgotten_details = []
    if result.issue_class in {'direct_memory_issue', 'observed_retrieval_issue'}:
        if not result.observed_symptoms:
            result.issue_class = 'related_context'
        else:
            result.search_relevance = 'yes'
            # The full original record is exact source text when the model paraphrases a span.
            # Later sample review checks whether it actually supports this decision.
            if not result.issue_quote:
                result.issue_quote = row.text
            if not result.result_quote:
                result.result_quote = result.issue_quote
    if result.issue_class in {'unrelated', 'retrieval_success', 'search_request', 'related_context'}:
        result.observed_symptoms = []
        result.issue_quote = None
        result.result_quote = None
    return result
