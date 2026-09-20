"""Source-grounded labels for the assignment's incomplete-memory research."""
from typing import Literal
import re

from pydantic import BaseModel, ConfigDict, Field

ANALYSIS_VERSION = 'retrieval-v2'
MODEL = 'gpt-4o-mini'


class RetrievalAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    review_id: str
    relevance: Literal['unrelated', 'retrieval', 'incomplete_memory']
    rationale: str = Field(description='One short explanation of the label, grounded in the record.')
    evidence_quotes: list[str] = Field(description='1-3 short verbatim spans supporting a relevant label; empty if unrelated.')
    remembered_clues: list[str] = Field(description='Verbatim spans specifying remembered people, objects, places, events, dates, or visual details.')
    missing_details: list[str] = Field(description='Verbatim spans explicitly saying what is forgotten or unknown. Never infer this from silence.')
    attempted_queries: list[str] = Field(description='Verbatim spans of queries or search actions actually attempted, not advice or hypothetical requests.')
    workarounds: list[str] = Field(description='Verbatim spans of actions actually used instead of the failing search.')
    outcome: Literal['failure', 'success', 'mixed', 'not_reported']
    failure_mechanism: Literal['query_formulation', 'poor_matches', 'missing_index_or_metadata', 'navigation_or_scrolling', 'search_unavailable', 'other', 'not_reported']
    failure_evidence: str | None = Field(description='Short verbatim span supporting the failure mechanism; null if not reported.')


class AssessmentBatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessments: list[RetrievalAssessment]


class UnrelatedTransportAssessment(BaseModel):
    """Unrelated feedback has no retrieval outcome or memory fields to infer."""
    model_config = ConfigDict(extra='forbid')
    review_id: str
    relevance: Literal['unrelated']
    rationale: str


class RelevantTransportAssessment(RetrievalAssessment):
    relevance: Literal['retrieval', 'incomplete_memory']


class TransportBatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessments: list[UnrelatedTransportAssessment | RelevantTransportAssessment]


def canonical_source_span(span, text):
    if not span.strip():
        return None
    if span in text:
        return span
    # Match whitespace differences only, then retain the ORIGINAL source characters.
    pattern = r'\s+'.join(re.escape(word) for word in span.split())
    match = re.search(pattern, text)
    return match.group(0) if match else None


def validate_assessment(result, text):
    """Reject invented quotations and labels that lack their required evidence."""
    for field in ('evidence_quotes', 'remembered_clues', 'missing_details', 'attempted_queries', 'workarounds'):
        aligned = []
        for span in getattr(result, field):
            original = canonical_source_span(span, text)
            if original is None:
                raise ValueError(f'{result.review_id}: Evidence must be an exact nonempty source span; invalid span: {span[:120]!r}')
            aligned.append(original)
        setattr(result, field, aligned)
    if result.failure_evidence is not None:
        original = canonical_source_span(result.failure_evidence, text)
        if original is None:
            raise ValueError(f'{result.review_id}: Evidence must be an exact nonempty source span; invalid failure_evidence')
        result.failure_evidence = original
    spans = (result.evidence_quotes + result.remembered_clues + result.missing_details
             + result.attempted_queries + result.workarounds)
    if result.failure_evidence is not None:
        spans.append(result.failure_evidence)
    if result.relevance != 'unrelated' and not result.evidence_quotes:
        raise ValueError('Relevant assessments require source evidence')
    if result.relevance == 'incomplete_memory' and not (result.remembered_clues and result.missing_details):
        raise ValueError(f'{result.review_id}: Incomplete memory requires explicitly remembered and missing details; use retrieval if memory details are not explicitly stated')
    if any(re.fullmatch(r'\d{4}', span.strip()) for span in result.missing_details):
        raise ValueError(f'{result.review_id}: A stated year is not evidence of forgotten information; copy the explicit uncertainty phrase or leave missing_details empty')
    if result.failure_mechanism != 'not_reported' and not result.failure_evidence:
        raise ValueError('Failure mechanisms require source evidence')
    if result.relevance == 'unrelated' and (spans or result.outcome != 'not_reported' or result.failure_mechanism != 'not_reported'):
        raise ValueError('Unrelated feedback cannot contribute retrieval findings')
    return result
