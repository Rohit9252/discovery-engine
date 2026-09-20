"""Source-linked answers from the current Phase 1 issue decisions."""
import html
import re
from collections import defaultdict

from src.process.issue_dashboard import STAGES, issue_snapshot
from src.process.source_audit import active_reviews


STOPWORDS = {
    'a', 'about', 'an', 'and', 'are', 'can', 'do', 'does', 'for', 'from', 'google',
    'how', 'in', 'is', 'issue', 'issues', 'of', 'on', 'photo', 'photos', 'problem',
    'problems', 'retrieval', 'search', 'the', 'their', 'there', 'to', 'user', 'users',
    'what', 'when', 'where', 'why', 'with',
}

SPECIFIC_TOPICS = {
    'face', 'faces', 'person', 'pet', 'dog', 'cat', 'date', 'time', 'location',
    'place', 'album', 'screenshot', 'video', 'ocr', 'text', 'ask', 'gemini',
    'scroll', 'ranking', 'filter', 'metadata', 'filename', 'caption', 'backup',
}

REASON_EXPLANATIONS = {
    'poor_matches': 'The searched-for photo is absent, only partly returned, or buried among unrelated matches.',
    'metadata_or_index': 'A reported date, place, or indexing mismatch makes an existing photo hard to find.',
    'face_group': 'Person or face grouping does not lead to the expected photos.',
    'navigation': 'Browsing or evaluating the returned photos makes the target hard to locate.',
    'query_formulation': 'The user struggles to express remembered clues in a usable search.',
    'search_unavailable': 'Search itself is unavailable or fails to return usable results.',
    'ai_assistant': 'Ask Photos or another AI search flow mishandles the request or its follow-up.',
    'other': 'The report describes another concrete retrieval barrier.',
}


def terms(value):
    return {word for word in re.findall(r'[a-z0-9]+', value.lower()) if len(word) > 2 and word not in STOPWORDS}


def asks_for_major_reasons(question):
    words = set(re.findall(r'[a-z0-9]+', question.lower()))
    broad = bool(words & {'why', 'reasons', 'reason', 'major', 'main', 'top', 'common', 'overall'})
    subject = bool(words & {'retrieval', 'retrieve', 'search', 'searching', 'find', 'finding', 'photos', 'photo'})
    return broad and subject and not bool(words & SPECIFIC_TOPICS)


def source_entry(index, key, issue, source):
    return {
        'index': index, 'id': key, 'source': source.source,
        'source_label': source.source.replace('_', ' ').title(),
        'url': source.url, 'snippet': issue.issue_quote[:160],
        'full_text': source.text, 'failure_stage': STAGES[issue.failure_stage],
    }


def representative(rows, by_id, used_urls):
    def quality(item):
        key, issue = item
        source = by_id[key]
        return (
            bool(source.url and source.url not in used_urls),
            issue.disposition == 'direct_memory_issue',
            sum(bool(getattr(issue, field)) for field in (
                'photo_target', 'remembered_clue', 'missing_detail',
                'attempted_action', 'workaround')),
            min(len(issue.issue_quote or ''), 220),
            key,
        )
    return max(rows, key=quality)


def major_reasons_answer(question, status, issues, by_id):
    if not issues:
        return {'answer': 'No source-backed retrieval issues have been classified yet.',
                'sources': [], 'rewritten_question': question}
    groups = defaultdict(list)
    for key, issue in issues.items():
        groups[issue.failure_stage].append((key, issue))
    ranked = sorted(((stage, rows) for stage, rows in groups.items()
                     if stage != 'unknown'), key=lambda item: (-len(item[1]), item[0]))
    threshold = 2 if len(issues) >= 20 else 1
    major = [(stage, rows) for stage, rows in ranked if len(rows) >= threshold]
    less_frequent = [(stage, rows) for stage, rows in ranked if len(rows) < threshold]
    lines = [
        f'**What people report:** {len(issues)} of {status["analyzed_count"]} AI-screened '
        'feedback records describe a concrete photo retrieval problem. '
        'The largest reported barrier groups in this catalog are:',
    ]
    sources = []
    used_urls = set()
    for stage, rows in major:
        key, issue = representative(rows, by_id, used_urls)
        source = by_id[key]
        if source.url:
            used_urls.add(source.url)
        index = len(sources) + 1
        quote = html.escape(' '.join(issue.issue_quote.split()))
        record_count = f'{len(rows)} feedback record{"s" if len(rows) != 1 else ""}'
        lines.append(f'{index}. **{html.escape(STAGES[stage])}** '
                     f'({record_count}). {REASON_EXPLANATIONS[stage]} '
                     f'Example: “{quote}” [{index}].')
        sources.append(source_entry(index, key, issue, source))
    if less_frequent:
        labels = ', '.join(f'{STAGES[stage]} ({len(rows)})' for stage, rows in less_frequent)
        lines.append(f'Less frequent reported barriers in this set: {html.escape(labels)}.')
    unclear = len(groups['unknown'])
    if unclear:
        lines.append(f'{unclear} additional issue record{"s" if unclear != 1 else ""} '
                     'report a problem without enough detail to identify its barrier.')
    lines.append(
        f'**Phase 1 limit:** {status["incomplete_memory_count"]} of these issue records explicitly '
        'state a forgotten detail about the target photo. '
        f'Assessment remaining: {status["pending_count"]} pending and '
        f'{status["failed_count"]} failed. '
        'These are feedback-record counts, not numbers of '
        'users or failed sessions. Reports show what went wrong for users; they do not prove '
        'Google Photos\' internal technical causes.'
    )
    return {'answer': '\n\n'.join(lines), 'sources': sources,
            'rewritten_question': question}


def answer_issue_question(session, question):
    reviews = active_reviews(session).order_by('id').all()
    status, issues, _ = issue_snapshot(session, reviews)
    by_id = {row.id: row for row in reviews}
    if asks_for_major_reasons(question):
        return major_reasons_answer(question, status, issues, by_id)
    query_terms = terms(question)
    ranked = []
    for key, issue in issues.items():
        source = by_id[key]
        focused = ' '.join(filter(None, (
            issue.issue_quote, issue.photo_target, issue.remembered_clue,
            issue.missing_detail, issue.attempted_action, STAGES[issue.failure_stage],
        )))
        score = 3 * len(query_terms & terms(focused)) + len(query_terms & terms(source.text))
        if query_terms and score == 0:
            continue
        ranked.append((score, issue.disposition == 'direct_memory_issue', key, issue, source))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    selected = ranked[:5]
    if not selected:
        message = ('No source-backed reported issue candidates have been classified yet.' if not issues else
                   'I could not find a source-backed reported issue matching that question in the classified records.')
        return {'answer': message, 'sources': [], 'rewritten_question': question}

    lines = [
        f'**{len(selected)} source-backed reported issue example{"s" if len(selected) != 1 else ""}** '
        '(AI-screened; not human reviewed):',
    ]
    sources = []
    for number, (_, _, key, issue, source) in enumerate(selected, 1):
        label = ('Explicit incomplete-memory case' if issue.disposition == 'direct_memory_issue'
                 else 'Retrieval issue; memory gap not established')
        quote = html.escape(' '.join(issue.issue_quote.split()))
        lines.append(f'{number}. **{html.escape(STAGES[issue.failure_stage])}** [{number}]: '
                     f'“{quote}” ({label}).')
        sources.append(source_entry(number, key, issue, source))
    lines.append('These records report user experiences. The technical cause and prevalence still need validation.')
    return {'answer': '\n\n'.join(lines), 'sources': sources, 'rewritten_question': question}
