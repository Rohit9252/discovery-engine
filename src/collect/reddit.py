"""Date-paginated archive collection with local title/body keyword selection."""
import time
from src.collect.config import SUBREDDITS, matched_terms, mentions_product
from src.collect.http_client import get_json, CollectionError
from src.collect.storage import save_records

BASE_URL = 'https://arctic-shift.photon-reddit.com/api'


def scrape_posts_by_keyword(subreddits=SUBREDDITS, keywords=None, limit=100, pages=5, after='2024-01-01', receipt=None):
    receipt = receipt if receipt is not None else {}
    receipt.setdefault('errors', [])
    receipt.setdefault('scanned', 0)
    all_posts = {}
    for subreddit in subreddits:
        before = None
        seen = set()
        for page in range(pages):
            params = {'subreddit':subreddit, 'limit':min(limit,100), 'sort':'desc', 'after':after}
            if before is not None:
                params['before'] = before
            try:
                items = get_json(BASE_URL + '/posts/search', params).get('data') or []
            except CollectionError as exc:
                receipt['errors'].append({'subreddit':subreddit, 'page':page + 1, 'error':str(exc)})
                break
            receipt['scanned'] += len(items)
            new_ids = {row.get('id') for row in items} - seen
            if not new_ids:
                break
            seen.update(new_ids)
            for row in items:
                title = row.get('title') or ''
                body = row.get('selftext') or ''
                if body in ('[removed]', '[deleted]'):
                    body = ''
                text = (title + '\n\n' + body).strip()
                terms = matched_terms(text)
                if keywords is not None:
                    terms = [term for term in terms if term in keywords]
                if not row.get('id') or not terms:
                    continue
                if subreddit.lower() != 'googlephotos' and not mentions_product(text):
                    continue
                permalink = row.get('permalink') or f'/r/{subreddit}/comments/{row["id"]}/'
                all_posts[row['id']] = {
                    'id':row['id'], 'title':title, 'selftext':body, 'text':text,
                    'created_utc':row.get('created_utc'), 'score':row.get('score'),
                    'url':'https://www.reddit.com' + permalink,
                    'subreddit':subreddit, 'source':'reddit', 'matched_terms':terms,
                    'product_context_verified':True, 'record_type':'post',
                }
            timestamps = [row['created_utc'] for row in items if row.get('created_utc') is not None]
            if len(items) < min(limit,100) or not timestamps:
                break
            cursor = min(timestamps)
            if before is not None and cursor >= before:
                break
            before = cursor
            time.sleep(0.5)
    receipt['strategy'] = 'recent_subreddit_pages_then_local_title_and_body_keywords'
    receipt['bounded_pages_per_subreddit'] = pages
    receipt['after'] = after
    receipt['sampling_limit'] = 'Recent date-ordered page cap; not exhaustive keyword search. Equal-timestamp page boundaries may omit records.'
    return all_posts


def scrape_comments_from_threads(posts, max_results=100, pages=2, receipt=None):
    """Only accept parent posts actually retrieved with verified product context."""
    receipt = receipt if receipt is not None else {}
    receipt.setdefault('errors', [])
    comments = {}
    for post in posts:
        if not isinstance(post, dict) or not post.get('product_context_verified'):
            raise ValueError('Comments require a retrieved, product-context-verified parent post')
        post_id = post['id']
        before = None
        for page in range(pages):
            params = {'link_id':post_id, 'limit':min(max_results,100), 'sort':'desc'}
            if before is not None:
                params['before'] = before
            try:
                items = get_json(BASE_URL + '/comments/search',params).get('data') or []
            except CollectionError as exc:
                receipt['errors'].append({'post_id':post_id,'error':str(exc)})
                break
            for row in items:
                body = (row.get('body') or '').strip()
                if not row.get('id') or body in ('[removed]','[deleted]') or not body:
                    continue
                key = 'comment_' + row['id']
                comments[key] = {
                    'id':key,'text':body,'created_utc':row.get('created_utc'),
                    'subreddit':post['subreddit'],'source':'reddit','record_type':'comment',
                    'url':f'https://www.reddit.com/comments/{post_id}/_/{row["id"]}/',
                    'parent_post_id':post_id,'parent_id':row.get('parent_id'),
                    'context_title':post['title'],'product_context_verified':True,
                    'matched_terms':matched_terms(body),
                }
            stamps = [row['created_utc'] for row in items if row.get('created_utc') is not None]
            if len(items) < min(max_results,100) or not stamps:
                break
            cursor = min(stamps)
            if before is not None and cursor >= before:
                break
            before = cursor
            time.sleep(0.5)
    return comments


def save_reddit_data(records, output_file='data/raw/reddit_posts.json'):
    return save_records(records, output_file)
