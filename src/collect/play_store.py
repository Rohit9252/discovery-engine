from google_play_scraper import reviews, Sort
import json
import logging
from pathlib import Path
import time
from src.collect.storage import save_records

# Setup standard logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_play_store_reviews(app_id="com.google.android.apps.photos", lang='en', country='us', count=1000, receipt=None):
    """
    Scrape recent reviews from Google Play Store.
    
    Args:
        app_id (str): The Google Play Store app package ID.
        lang (str): Language code.
        country (str): Country code.
        count (int): Number of reviews to fetch.
        
    Returns:
        list: A list of dictionaries containing review data.
    """
    logging.info(f"Starting scraping for Play Store app: {app_id} (Target: {count} reviews)")
    receipt = receipt if receipt is not None else {}
    receipt.setdefault('errors', [])
    collected = {}
    continuation_token = None
    while len(collected) < count:
        result = None
        for attempt in range(3):
            try:
                options = dict(lang=lang, country=country, sort=Sort.NEWEST,
                               count=min(200, count-len(collected)), filter_score_with=None)
                if continuation_token is not None:
                    options['continuation_token'] = continuation_token
                result, next_token = reviews(app_id, **options)
                break
            except Exception as exc:
                if attempt == 2:
                    receipt['errors'].append({'country':country,'error_type':type(exc).__name__})
                else:
                    time.sleep(2 ** attempt)
        if result is None:
            break
        before = len(collected)
        for row in result:
            enriched = {**row, 'app_id':app_id, 'country':country, 'language':lang,
                        'product_context_verified':True}
            from src.collect.storage import record_key
            collected[record_key(row)] = enriched
        if not result or len(collected) == before or next_token is None:
            break
        continuation_token = next_token
    receipt['coverage'] = 'Recent reviews across all star ratings; no server-side keyword filtering.'
    return list(collected.values())

def save_reviews(reviews_data, output_file="data/raw/play_store_reviews.json"):
    """
    Save the scraped reviews to a JSON file.
    
    Args:
        reviews_data (list): The list of review dictionaries.
        output_file (str): The path to the output JSON file.
    """
    return save_records(reviews_data, output_file)

