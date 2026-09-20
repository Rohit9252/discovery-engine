"""Present only versioned, source-grounded reported retrieval issues."""
from collections import Counter
from datetime import timedelta

from src.process.db import ResearchRun, ResearchRunProgress
from src.process.issue_schema import ISSUE_DISPOSITIONS, ISSUE_VERSION
from src.process.issue_store import current_issue_analysis, decoded_issues
from src.process.paths import API_PAUSE_FILE
from src.process.research_store import utc_now


STAGES = {
    'poor_matches': 'Poor or missing search matches',
    'metadata_or_index': 'Date, location, or index mismatch',
    'face_group': 'Incorrect person grouping',
    'navigation': 'Browsing or result evaluation barrier',
    'query_formulation': 'Difficulty expressing a search',
    'search_unavailable': 'Search unavailable',
    'ai_assistant': 'AI assistant or Ask Photos failure',
    'other': 'Other reported retrieval barrier',
    'unknown': 'Reported issue, stage unclear',
}


def issue_snapshot(session, reviews):
    analyses = current_issue_analysis(session, reviews)
    results = decoded_issues(analyses)
    issues = {key: row for key, row in results.items() if row.disposition in ISSUE_DISPOSITIONS}
    direct = sum(row.disposition == 'direct_memory_issue' for row in issues.values())
    failed = sum(row.status == 'failed' for row in analyses.values())
    pending = len(reviews) - len(results) - failed
    latest = session.query(ResearchRun).filter_by(version=ISSUE_VERSION).order_by(ResearchRun.started_at.desc()).first()
    progress = session.get(ResearchRunProgress, latest.id) if latest else None
    running = bool(latest and latest.status == 'running' and latest.updated_at > utc_now() - timedelta(minutes=10))
    if not reviews:
        state = 'no_data'
    elif running:
        state = 'running'
    elif API_PAUSE_FILE.exists():
        state = 'paused'
    elif pending or failed:
        state = 'partial' if analyses else 'pending_review'
    else:
        state = 'completed'
    title = {
        'no_data': 'No feedback available',
        'running': 'Checking reported retrieval issues',
        'paused': 'Issue analysis paused',
        'partial': 'Issue evidence review in progress',
        'pending_review': 'Issue evidence ready for analysis',
        'completed': 'AI issue screening complete',
    }[state]
    error_counts = Counter(row.error for row in analyses.values() if row.status == 'failed')
    provider_limits = error_counts.get('provider_rate_limit', 0)
    validation = sum(count for code, count in error_counts.items() if (code or '').startswith('validation_'))
    by_disposition = Counter(row.disposition for row in results.values())
    status = {
        'state': state, 'title': title, 'version': ISSUE_VERSION,
        'total': len(reviews), 'analyzed_count': len(results), 'failed_count': failed,
        'pending_count': pending, 'retrieval_count': len(issues),
        'incomplete_memory_count': direct, 'adjacent_issue_count': len(issues) - direct,
        'context_count': by_disposition['context'], 'unrelated_count': by_disposition['unrelated'],
        'insufficient_context_count': by_disposition['insufficient_context'],
        'known_mechanism_count': sum(row.failure_stage != 'unknown' for row in issues.values()),
        'unclear_failure_count': sum(row.failure_stage == 'unknown' for row in issues.values()),
        'no_reported_failure_count': 0,
        'failed_provider_limit_count': provider_limits,
        'failed_evidence_validation_count': validation,
        'failed_batch_output_count': 0,
        'failed_other_count': failed - provider_limits - validation,
        'validated_retrieval_count': None, 'human_reviewed_count': 0,
        'last_updated': latest.updated_at.isoformat() + 'Z' if latest else None,
        'run_phase': progress.phase if progress else None,
        'phase_scheduled': progress.scheduled if progress else None,
        'phase_done': progress.completed if progress else None,
        'phase_failed': progress.failed if progress else None,
        'details': [
            f'{len(results):,} of {len(reviews):,} active records have a new issue decision; {pending:,} await this pass and {failed:,} need retry.',
            f'{len(issues):,} source-backed reported issue candidates: {direct:,} explicitly involve incomplete memory; {len(issues) - direct:,} are adjacent retrieval problems.',
            f'{by_disposition["context"]:,} context or positive records and {by_disposition["unrelated"]:,} unrelated records are excluded from issue findings.',
            'AI-screened issue reports are research candidates, not human-verified product diagnoses or session rates.',
        ],
        'next_steps': [
            'Inspect source-linked issue reports and audit ambiguous classifications.',
            'Keep a reported symptom separate from a proposed technical cause or solution.',
            'Use direct incomplete-memory cases to design the required user interviews.',
        ],
    }
    return status, issues, results


def apply_issue_dashboard(session, reviews, data, insights):
    status, issues, _ = issue_snapshot(session, reviews)
    by_id = {row.id: row for row in reviews}
    groups = {}
    for key, row in issues.items():
        groups.setdefault(row.failure_stage, []).append((key, row))
    ranked = sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0]))
    data['research_status'] = status
    data['analysis_method'] = 'source_grounded_issue_assessment'
    data['themes'] = [{'theme': STAGES[stage], 'count': len(rows)} for stage, rows in ranked]
    data['themes_count'] = len(ranked)
    data['failure_stages'] = list(data['themes'])
    data['failure_stages_count'] = len(ranked)
    data['other_retrieval_evidence'] = []
    data['outcomes'] = {'reported_issue': len(issues)}
    data['evidence_field_counts'] = {
        field: sum(bool(getattr(row, field)) for row in issues.values())
        for field in ('remembered_clue', 'missing_detail', 'attempted_action', 'workaround')
    }
    cards = []
    for stage, rows in ranked:
        key, row = sorted(rows, key=lambda pair: (
            pair[1].disposition != 'direct_memory_issue',
            -sum(bool(getattr(pair[1], field)) for field in (
                'remembered_clue', 'missing_detail', 'attempted_action', 'workaround')),
            pair[0],
        ))[0]
        source = by_id[key]
        cards.append({
            'title': STAGES[stage], 'summary': (
                f'{len(rows)} AI-screened reported issue records in this group. '
                'These are feedback records, not users or sessions.'),
            'quote': row.issue_quote, 'quote_truncated': False, 'evidence_id': key,
            'source': source.source, 'url': source.url, 'review_count': len(rows),
            'theme_tag': 'Explicit incomplete memory' if row.disposition == 'direct_memory_issue'
                         else 'Retrieval issue; memory gap unproven',
        })
    insights['insights'] = cards[:4]
    insights['strongest_signal'] = {
        'title': status['title'],
        'description': (f'{len(issues)} AI-screened, source-backed reported issue candidates '
                        f'among {status["analyzed_count"]} '
                        'new issue decisions. Human review is still required.'),
        'pain_points': status['details'], 'opportunities': status['next_steps'],
    }
    return data, insights


def issue_evidence_page(session, reviews, category='all', offset=0, limit=12):
    status, issues, _ = issue_snapshot(session, reviews)
    by_id = {row.id: row for row in reviews}
    rows = [(key, row) for key, row in issues.items()
            if category == 'all' or row.disposition == category]
    rows.sort(key=lambda pair: (pair[1].disposition != 'direct_memory_issue', pair[0]))
    return {
        'total': len(rows), 'offset': offset, 'limit': limit, 'analysis_status': status['state'],
        'records': [dict(row.model_dump(), source=by_id[key].source, url=by_id[key].url,
                         source_text=by_id[key].text, validation='AI-screened; source spans checked; not human reviewed')
                    for key, row in rows[offset:offset + limit]],
    }
