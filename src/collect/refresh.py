"""Run bounded source refreshes and persist honest source-specific receipts."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from dotenv import load_dotenv

from src.collect import reddit, youtube, app_store, play_store
from src.collect.config import SUBREDDITS, RETRIEVAL_TERMS, YOUTUBE_VIDEO_IDS
from src.collect.storage import save_run
from src.process.paths import PROJECT_ROOT


def collect_source(source):
    receipt = {'errors': [], 'selection_terms':list(RETRIEVAL_TERMS)}
    if source == 'reddit':
        posts = reddit.scrape_posts_by_keyword(pages=5, receipt=receipt)
        ranked = sorted(posts.values(), key=lambda row:(
            'ask photos' in row['text'].lower(), len(row.get('selftext',''))), reverse=True)
        parents = ranked[:12]
        comments = reddit.scrape_comments_from_threads(parents, pages=2, receipt=receipt)
        receipt['subreddits'] = list(SUBREDDITS)
        receipt['comment_parent_ids'] = [row['id'] for row in parents]
        records = list(posts.values()) + list(comments.values())
    elif source == 'play_store':
        records = []
        for country in ('us','in'):
            records.extend(play_store.scrape_play_store_reviews(country=country,count=2000,receipt=receipt))
        receipt['app_id'] = 'com.google.android.apps.photos'
        receipt['countries'] = ['us','in']
    elif source == 'app_store':
        records = []
        for country in ('us','in'):
            records.extend(app_store.normalize(app_store.scrape_via_rss(pages=6,country=country,receipt=receipt),'rss'))
        receipt['app_id'] = 962194608
        receipt['countries'] = ['us','in']
        receipt['coverage'] = 'Public Apple review RSS, newest first, capped at six pages per storefront. URLs identify the app page, not individual reviews.'
    elif source == 'youtube':
        key = os.getenv('YOUTUBE_API_KEY')
        if not key:
            receipt['errors'].append({'error':'YOUTUBE_API_KEY is not configured'})
            records = []
        else:
            titles = youtube.verify_videos(key,YOUTUBE_VIDEO_IDS)
            receipt['verified_videos'] = titles
            receipt['rejected_or_unavailable_videos'] = [video for video in YOUTUBE_VIDEO_IDS if video not in titles]
            records = youtube.get_youtube_comments(key,list(titles),pages=3,receipt=receipt,verified_titles=titles)
    else:
        raise ValueError('Unsupported source')
    receipt['status'] = 'partial' if receipt['errors'] and records else 'failed' if receipt['errors'] else 'succeeded' if records else 'empty'
    return save_run(source,records,receipt,PROJECT_ROOT / 'data' / 'raw')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sources',nargs='+',choices=['reddit','play_store','app_store','youtube'],default=['reddit','play_store','app_store','youtube'])
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / '.env')
    summary = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(collect_source, source):source for source in args.sources}
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = save_run(source,[],{'status':'failed','errors':[{'error_type':type(exc).__name__}]},PROJECT_ROOT / 'data' / 'raw')
            summary.append(result)
            print(json.dumps(result,ensure_ascii=True),flush=True)
    target = PROJECT_ROOT / 'data' / 'collection-runs' / 'latest-summary.json'
    target.write_text(json.dumps(summary,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
