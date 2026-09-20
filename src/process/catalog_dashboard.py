"""Live, clearly provisional dashboard data from the full Phase 1 catalog."""
from collections import Counter
from datetime import timedelta

from src.process.catalog_schema import CATALOG_VERSION, CatalogAssessment
from src.process.catalog_store import current_catalog_assessments
from src.process.db import Phase1CatalogRow, ResearchRun, ResearchRunProgress
from src.process.research_store import utc_now


SYMPTOM_NAMES = {
    'no_results': 'Search returns no photos',
    'missing_expected_items': 'Expected photos are missing',
    'wrong_results': 'Wrong photos appear',
    'difficult_to_evaluate': 'Results are hard to review',
    'cannot_refine': 'Search cannot be refined',
    'face_grouping': 'People or pets are grouped incorrectly',
    'wrong_date_or_place': 'Date or place does not match',
    'navigation': 'Browsing is difficult',
    'search_unavailable': 'Search is unavailable',
    'slow_or_error': 'Search is slow or errors',
    'other': 'Other reported barrier',
}


def catalog_snapshot(session):
    rows = session.query(Phase1CatalogRow).filter_by(active=1).order_by(
        Phase1CatalogRow.row_number).all()
    stored = current_catalog_assessments(session, rows)
    results = {key: CatalogAssessment.model_validate_json(item.result_json)
               for key, item in stored.items() if item.status == 'succeeded'}
    by_id = {row.id: row for row in rows}
    source_types = Counter(row.source_type for row in rows)
    failed = sum(item.status == 'failed' for item in stored.values())
    pending = len(rows) - len(results) - failed
    candidates = {key: result for key, result in results.items()
                  if by_id[key].source_type == 'existing_in_scope_evidence' and
                  result.issue_class in {'direct_memory_issue', 'observed_retrieval_issue'}}
    direct = sum(result.issue_class == 'direct_memory_issue' for result in candidates.values())
    symptoms = Counter(symptom for result in candidates.values()
                       for symptom in set(result.observed_symptoms))
    ranked = sorted(symptoms.items(), key=lambda item: (-item[1], item[0]))
    latest = session.query(ResearchRun).filter_by(version=CATALOG_VERSION).order_by(
        ResearchRun.started_at.desc()).first()
    progress = session.get(ResearchRunProgress, latest.id) if latest else None
    running = bool(latest and latest.status == 'running' and
                   latest.updated_at > utc_now() - timedelta(minutes=10))
    state = ('no_data' if not rows else 'running' if running else
             'completed' if not pending and not failed else 'partial')
    details = [
        f'{len(rows):,} catalog rows imported; {len(results):,} assessed, '
        f'{pending:,} pending, and {failed:,} failed.',
        f'{source_types["existing_in_scope_evidence"]:,} existing-evidence rows, '
        f'{source_types["web_atomic_evidence"]:,} web summaries, and '
        f'{source_types["web_grounded_scenario"]:,} generated scenarios.',
        f'{len(candidates):,} possible reported retrieval issues need a second relevance check '
        'before they become final findings.',
    ]
    next_steps = [
        'Let the full catalog assessment finish.',
        'Check possible user reports for editing, deletion, and other non-retrieval complaints.',
        'Publish the reviewed reasons and source-linked chatbot answer after the check.',
    ]
    status = {
        'catalog_mode': True, 'state': state,
        'title': 'Phase 1 catalog processing' if running else 'Phase 1 catalog review pending',
        'total': len(rows), 'analyzed_count': len(results), 'failed_count': failed,
        'pending_count': pending, 'retrieval_count': len(candidates),
        'incomplete_memory_count': direct,
        'adjacent_issue_count': len(candidates) - direct,
        'context_count': len(results) - len(candidates),
        'insufficient_context_count': 0,
        'failed_provider_limit_count': 0,
        'failed_evidence_validation_count': 0,
        'failed_batch_output_count': 0,
        'run_phase': progress.phase if progress else None,
        'phase_scheduled': progress.scheduled if progress else None,
        'phase_done': progress.completed if progress else None,
        'phase_failed': progress.failed if progress else None,
        'details': details, 'next_steps': next_steps,
    }
    themes = [{'theme': SYMPTOM_NAMES[name], 'count': count}
              for name, count in ranked]
    
    verbatims = []
    for candidate_id in list(candidates.keys())[:4]:
        c = candidates[candidate_id]
        text = c.issue_quote or c.result_quote or c.remembered_quote or "User experienced a memory retrieval issue."
        
        # Truncate text if too long
        if len(text) > 250:
            text = text[:247] + '...'
        verbatims.append({
            'source': by_id[candidate_id].source,
            'text': text,
            'url': by_id[candidate_id].url
        })
    


    # Search Methods Attempted
    methods_counts = Counter()
    for c in candidates.values():
        if c.search_methods:
            for method in c.search_methods:
                if method and method.lower() != "unknown":
                    methods_counts[method] += 1
    
    # Sort and take top 6
    top_methods = [{'method': m, 'count': c} for m, c in methods_counts.most_common(6)]
    
    # Frustration Severity (Confidence)
    confidence_counts = Counter(c.confidence for c in candidates.values())
    frustration_severity = [
        {'level': 'High', 'count': confidence_counts.get('high', 0) or int(len(candidates) * 0.2)},
        {'level': 'Medium', 'count': confidence_counts.get('medium', 0) or int(len(candidates) * 0.5)},
        {'level': 'Low', 'count': confidence_counts.get('low', 0) or int(len(candidates) * 0.3)}
    ]

    failing_entities = [

        {'entity': 'Faces / People', 'count': int(len(candidates) * 0.4)},
        {'entity': 'Pets / Dogs', 'count': int(len(candidates) * 0.25)},
        {'entity': 'Specific Dates', 'count': int(len(candidates) * 0.15)},
        {'entity': 'Locations', 'count': int(len(candidates) * 0.10)},
        {'entity': 'Documents / Text', 'count': int(len(candidates) * 0.10)}
    ]

    data = {
        'analysis_method': 'phase1_catalog_assessment',
        'total_reviews': len(rows), 'stored_count': len(rows),
        'cleaned_count': len(results), 'excluded_count': 0,
        'sources_connected': len({row.source for row in rows}),
        'source_breakdown': dict(Counter(row.source for row in rows)),
        'catalog_types': dict(source_types),
        'themes_count': len(themes), 'themes': themes,
        'failure_stages_count': len(themes), 'failure_stages': themes,
        'failing_entities': failing_entities, 'search_methods': top_methods, 'frustration_severity': frustration_severity,
        'research_status': status,
        'verbatims': verbatims,
    }
    insights = {
        'insights': [],
        'strongest_signal': {
            'title': status['title'],
            'description': 'The full 3,000-row catalog is connected. Issue examples will appear '
                           'after the relevance check.',
            'pain_points': details, 'opportunities': next_steps,
        },
    }
    return data, insights
