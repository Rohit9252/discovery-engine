"""Explicit source targets and local candidate-selection terms."""
PLAY_APP_ID = 'com.google.android.apps.photos'
APPLE_APP_ID = 962194608
SUBREDDITS = ('googlephotos', 'GooglePixel', 'Android', 'photography')
RETRIEVAL_TERMS = (
    'search', 'find', 'finding', 'remember', 'scroll', 'ask photos',
    'gemini', 'old photos', 'screenshot', 'receipt', 'face grouping',
)
YOUTUBE_VIDEO_IDS = (
    'sJLrAhhH5sU', '4DNQp3jgT8c', 'pRtou8UlXk0', '5e76aH06NQA',
    'o44v9PZpH-I', 'zYMtLsAM_hQ', 'QNBQtgddtTI', 'qGq7Iw_dNn0',
)


def mentions_product(text):
    normalized = ' '.join(text.lower().split())
    return any(term in normalized for term in ('google photos', 'googlephotos', 'ask photos'))


def matched_terms(text):
    import re
    normalized = ' '.join(text.lower().split())
    return [term for term in RETRIEVAL_TERMS if re.search(r'\b' + re.escape(term) + r'\b', normalized)]
