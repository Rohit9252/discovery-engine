"""Verified video metadata and paginated public top-level comments."""
from src.collect.http_client import get_json, CollectionError
from src.collect.config import mentions_product
from src.collect.storage import save_records

API = 'https://www.googleapis.com/youtube/v3/'


def verify_videos(api_key, video_ids):
    payload = get_json(API + 'videos', {'key':api_key,'part':'snippet','id':','.join(video_ids)})
    verified = {}
    for item in payload.get('items', []):
        snippet = item.get('snippet', {})
        if mentions_product(snippet.get('title', '')):
            verified[item['id']] = snippet.get('title', '')
    return verified


def get_youtube_comments(api_key, video_ids, max_results=100, pages=3, receipt=None, verified_titles=None):
    receipt = receipt if receipt is not None else {}
    receipt.setdefault('errors', [])
    comments = {}
    for video_id in video_ids:
        token = None
        used_tokens = set()
        for page in range(pages):
            params = {'key':api_key,'part':'snippet','videoId':video_id,'textFormat':'plainText','maxResults':min(max_results,100)}
            if token:
                params['pageToken'] = token
            try:
                data = get_json(API + 'commentThreads',params)
            except CollectionError as exc:
                receipt['errors'].append({'video_id':video_id,'error':str(exc)})
                break
            for item in data.get('items', []):
                top = item['snippet']['topLevelComment']
                comment = top['snippet']
                key = top.get('id') or item['id']
                comments[key] = {
                    'id':key,'video_id':video_id,'text':comment.get('textOriginal') or comment.get('textDisplay'),
                    'author':comment.get('authorDisplayName'),'like_count':comment.get('likeCount'),
                    'published_at':comment.get('publishedAt'),
                    'url':f'https://www.youtube.com/watch?v={video_id}&lc={key}',
                    'context_title':(verified_titles or {}).get(video_id),
                    'product_context_verified':video_id in (verified_titles or {}),
                }
            token = data.get('nextPageToken')
            if not token or token in used_tokens:
                break
            used_tokens.add(token)
    receipt['coverage'] = 'Top-level comments only; replies are not collected. Page cap applies per verified video.'
    return list(comments.values())


def save_youtube_comments(comments, output_file='data/raw/youtube_comments.json'):
    return save_records(comments, output_file)
