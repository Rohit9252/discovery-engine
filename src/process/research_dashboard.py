"""Reconcile current, source-scoped assessments into inspectable research."""
from collections import Counter
from datetime import timedelta

from src.process.db import ResearchRun, ResearchRunProgress
from src.process.research_schema import ANALYSIS_VERSION
from src.process.research_store import current_analysis, decoded_results, utc_now
from src.process.paths import API_PAUSE_FILE

MECHANISMS = {
    'poor_matches': 'Poor or missing search matches',
    'missing_index_or_metadata': 'Missing index or metadata',
    'navigation_or_scrolling': 'Navigation and scrolling',
    'search_unavailable': 'Search unavailable',
    'query_formulation': 'Formulating a search',
    'other': 'Other reported retrieval issue',
}

OTHER_EVIDENCE = {
    'failure': 'Reported failure, cause unclear',
    'mixed': 'Mixed result, cause unclear',
    'success': 'Successful retrieval, no failure',
    'not_reported': 'Retrieval need, outcome not stated',
}


def interpretation_label(result):
    """Describe evidence without inventing a failure mechanism."""
    if result.failure_mechanism != 'not_reported':
        return MECHANISMS[result.failure_mechanism]
    return OTHER_EVIDENCE[result.outcome]


def research_snapshot(session, reviews):
    analyses = current_analysis(session, reviews)
    results = decoded_results(analyses)
    relevant = {key: row for key, row in results.items() if row.relevance != 'unrelated'}
    memory = sum(row.relevance == 'incomplete_memory' for row in relevant.values())
    known_mechanism = sum(row.failure_mechanism != 'not_reported' for row in relevant.values())
    unknown_failure = sum(row.failure_mechanism == 'not_reported' and row.outcome in {'failure', 'mixed'}
                          for row in relevant.values())
    no_failure = len(relevant) - known_mechanism - unknown_failure
    failed = sum(row.status == 'failed' for row in analyses.values())
    provider_limits = sum(row.status == 'failed' and row.error in {
        'OpenAIRateLimitError', 'RateLimitError', 'ProviderQuotaError', 'provider_rate_limit'}
        for row in analyses.values())
    evidence_errors = sum(row.status == 'failed' and (
        row.error == 'BatchValidationError' or (row.error or '').startswith('validation_'))
        for row in analyses.values())
    batch_errors = sum(row.status == 'failed' and row.error in {'ValueError', 'batch_output_invalid'}
                       for row in analyses.values())
    pending = len(reviews) - len(results) - failed
    latest = session.query(ResearchRun).filter_by(version=ANALYSIS_VERSION).order_by(ResearchRun.started_at.desc()).first()
    progress = session.get(ResearchRunProgress, latest.id) if latest else None
    running = latest is not None and latest.status == 'running' and latest.updated_at > utc_now() - timedelta(minutes=10)
    if not reviews:
        state, title = 'no_data', 'No feedback collected'
    elif API_PAUSE_FILE.exists():
        state, title = 'paused', 'Retrieval analysis paused at your request'
    elif running:
        state, title = 'running', ('Checking retrieval evidence' if progress and progress.phase == 'interpretation_check' else 'Retrieval analysis in progress')
    elif len(results) == len(reviews):
        state, title = 'completed', 'AI retrieval analysis complete'
    elif analyses or latest:
        state, title = 'partial', 'Retrieval analysis needs a resume'
    else:
        state, title = 'pending_review', 'Retrieval analysis ready to start'
    status = {
        'state': state, 'title': title, 'version': ANALYSIS_VERSION,
        'total': len(reviews), 'analyzed_count': len(results), 'failed_count': failed, 'pending_count': pending,
        'failed_provider_limit_count': provider_limits,
        'failed_evidence_validation_count': evidence_errors,
        'failed_batch_output_count': batch_errors,
        'failed_other_count': failed - provider_limits - evidence_errors - batch_errors,
        'retrieval_count': len(relevant), 'incomplete_memory_count': memory,
        'known_mechanism_count': known_mechanism, 'unclear_failure_count': unknown_failure,
        'no_reported_failure_count': no_failure,
        'unrelated_count': len(results) - len(relevant),
        'validated_retrieval_count': None, 'human_reviewed_count': 0,
        'last_updated': latest.updated_at.isoformat() + 'Z' if latest else None,
        'run_phase': progress.phase if progress else None,
        'phase_scheduled': progress.scheduled if progress else None,
        'phase_done': progress.completed if progress else None,
        'phase_failed': progress.failed if progress else None,
        'details': [
            f'{len(results):,} of {len(reviews):,} available records successfully analyzed; {pending:,} pending and {failed:,} failed.',
            f'Failed records awaiting retry: {provider_limits:,} provider limits, {evidence_errors:,} source evidence checks, {batch_errors:,} batch output checks, {failed - provider_limits - evidence_errors - batch_errors:,} other errors.',
            f'{len(relevant):,} AI-identified retrieval records; {memory:,} explicitly describe remembered clues and missing details.',
            f'{known_mechanism:,} name a supported failure mechanism; {unknown_failure:,} report a failure without enough detail to identify its cause; {no_failure:,} describe a retrieval need or success without a reported failure.',
            f'{len(results) - len(relevant):,} analyzed records concern other topics and are excluded from retrieval findings.',
            'All displayed evidence spans match their original source text. AI interpretation is not human validation.',
        ],
        'next_steps': [
            'Review the reported mechanisms and counts while classification quality is checked.',
            'Use explicitly stated clues, missing details, attempted searches and workarounds to compare problems.',
            'Test these research hypotheses in the assignment\'s 5-6 user interviews; public records are not session success rates.',
            'API calls are stopped. Resume only after you approve further API use.' if state == 'paused' else
            'Resume unfinished analysis after errors.' if state in {'partial', 'pending_review'} else
            ('Processing is active; this page updates automatically.' if running else 'Collect targeted stories where memory details are not reported.'),
        ],
    }
    return status, relevant, results


def apply_research_dashboard(session, reviews, data, insights):
    status, relevant, results = research_snapshot(session, reviews)
    # Retain the provisional view until there are real saved assessments.
    data['research_status'] = status
    if not results:
        insights['strongest_signal']['title'] = status['title']
        insights['strongest_signal']['pain_points'] = status['details']
        insights['strongest_signal']['opportunities'] = status['next_steps']
        return data, insights
    sources = {row.id: row for row in reviews}
    groups = {}
    other = Counter()
    for key, row in relevant.items():
        if row.failure_mechanism == 'not_reported':
            other[OTHER_EVIDENCE[row.outcome]] += 1
        else:
            groups.setdefault(row.failure_mechanism, []).append((key, row))
    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    data['themes'] = [{'theme': MECHANISMS[key], 'count': len(rows)} for key, rows in ranked]
    data['themes_count'] = len(ranked)
    data['failure_stages'] = [{'stage': MECHANISMS[key], 'count': len(rows)} for key, rows in ranked]
    data['failure_stages_count'] = len(data['failure_stages'])
    data['other_retrieval_evidence'] = [{'label': label, 'count': count}
                                        for label, count in sorted(other.items())]
    data['analysis_method'] = 'source_grounded_ai_assessment'
    data['outcomes'] = dict(Counter(row.outcome for row in relevant.values()))
    data['evidence_field_counts'] = {
        field: sum(bool(getattr(row, field)) for row in relevant.values())
        for field in ('remembered_clues', 'missing_details', 'attempted_queries', 'workarounds')
    }
    cards = []
    for mechanism, rows in ranked:
        key, result = sorted(rows, key=lambda item: (
            item[1].relevance != 'incomplete_memory',
            -sum(bool(getattr(item[1], field)) for field in ('remembered_clues', 'missing_details', 'attempted_queries', 'workarounds')),
            abs(len(item[1].failure_evidence or item[1].evidence_quotes[0]) - 100), item[0]))[0]
        source = sources[key]
        cards.append({
            'title': MECHANISMS[mechanism],
            'summary': f'{len(rows)} of {len(relevant)} AI-identified retrieval records in this group. Counts describe feedback records, not users or sessions.',
            'quote': result.failure_evidence or result.evidence_quotes[0], 'quote_truncated': False,
            'evidence_id': key, 'source': source.source, 'url': source.url,
            'review_count': len(rows), 'theme_tag': MECHANISMS[mechanism],
        })
    insights['insights'] = cards[:4]
    insights['strongest_signal'] = {
        'title': status['title'],
        'description': f'{len(relevant)} retrieval records identified in {len(results)} analyzed records across {len(set(sources[key].source for key in relevant))} sources. AI findings are research hypotheses for interview validation.',
        'pain_points': status['details'], 'opportunities': status['next_steps'],
    }
    return data, insights


def evidence_page(session, reviews, category='all', offset=0, limit=12):
    status, relevant, _ = research_snapshot(session, reviews)
    sources = {row.id: row for row in reviews}
    rows = [(key, result) for key, result in relevant.items()
            if category == 'all' or result.relevance == category]
    rows.sort(key=lambda item: (item[1].relevance != 'incomplete_memory', item[0]))
    return {
        'total': len(rows), 'offset': offset, 'limit': limit, 'analysis_status': status['state'],
        'records': [dict(result.model_dump(), source=sources[key].source, url=sources[key].url,
                         source_text=sources[key].text, interpretation=interpretation_label(result),
                         validation='AI assessed; literal evidence checked; not human reviewed')
                    for key, result in rows[offset:offset + limit]],
    }
