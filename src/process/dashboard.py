"""Provisional topic browsing, deliberately separate from validated research."""
import re
from collections import Counter

TOPIC_PATTERNS = {
    'Search': r'\b(search\w*|find|finding|retrieval|query|queries|keyword\w*|ocr|remember\w*|scroll\w*)\b',
    'Face Tagging': r'\b(face\w*|tagging|pet\w*|cats?|dogs?|grouping)\b',
    'Backup': r'\b(backup\w*|back up|sync\w*|upload\w*)\b',
    'UI Navigation': r'\b(navigat\w*|layout|locked folder|interface)\b',
    'Editing': r'\b(edit\w*|trim\w*|crop\w*|rotate|warp)\b',
    'Albums': r'\balbums?\b',
}


def build_dashboard(reviews):
    sources = Counter(review.source for review in reviews)
    groups = {
        topic: [review for review in reviews if re.search(pattern, review.text, re.I)]
        for topic, pattern in TOPIC_PATTERNS.items()
    }
    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    themes = [{'theme': topic, 'count': len(rows)} for topic, rows in ranked if rows]
    cards = []
    for topic, rows in ranked:
        if not rows:
            continue
        example = min(rows, key=lambda row: (abs(len(row.text) - 200), row.id))
        cards.append({
            'title': f'{topic} mentions',
            'summary': f'{len(rows)} feedback records match {topic.lower()} keywords. Not yet validated as retrieval problems.',
            'quote': example.text[:300],
            'quote_truncated': len(example.text) > 300,
            'evidence_id': example.id,
            'source': example.source,
            'url': example.url,
            'review_count': len(rows),
            'theme_tag': topic,
        })
        if len(cards) == 4:
            break
    data = {
        'total_reviews': len(reviews), 'cleaned_count': len(reviews),
        'sources_connected': len(sources), 'source_breakdown': dict(sources),
        'themes_count': len(themes), 'themes': themes,
        'failure_stages_count': None, 'failure_stages': [],
        'analysis_method': 'provisional_keyword_matches',
        'research_status': {
            'state': 'pending_review' if reviews else 'no_data',
            'validated_retrieval_count': None,
            'title': 'Analysis not yet reviewed' if reviews else 'No feedback collected',
            'details': [
                f'{len(reviews)} feedback records are available for review.' if reviews else 'Collect and clean public feedback before analyzing retrieval.',
                'Topics use keyword matching; they include positive and unrelated feedback.',
                'Source authenticity and memory-specific relevance have not been audited.',
                'The number of validated retrieval stories is unknown, not zero.',
            ],
            'next_steps': [
                f'Check source links and context for examples across all {len(sources)} available sources.',
                'Label remembered clues, explicitly forgotten details, attempted searches, outcomes, and workarounds.',
                'Compare AI labels with the reviewed sample and correct disagreements before analyzing the full corpus.',
                'Collect more relevant discussions only where the reviewed evidence leaves gaps.',
            ],
        },
    }
    hero = {
        'title': data['research_status']['title'],
        'description': f'{len(reviews)} stored feedback records across {len(sources)} sources. Topics overlap; counts are not user or session rates.',
        'pain_points': data['research_status']['details'],
        'opportunities': data['research_status']['next_steps'],
    }
    return data, {'insights': cards, 'strongest_signal': hero}
