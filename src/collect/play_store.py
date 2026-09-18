from google_play_scraper import reviews, Sort
import json
import logging
from pathlib import Path

# Setup standard logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_play_store_reviews(app_id="com.google.android.apps.photos", lang='en', country='us', count=1000):
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
    try:
        result, continuation_token = reviews(
            app_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=count,
            filter_score_with=None # Get all scores to find pain points regardless of star rating
        )
        logging.info(f"Successfully scraped {len(result)} reviews.")
        return result
    except Exception as e:
        logging.error(f"Error scraping Play Store: {e}")
        return []

def save_reviews(reviews_data, output_file="data/raw/play_store_reviews.json"):
    """
    Save the scraped reviews to a JSON file.
    
    Args:
        reviews_data (list): The list of review dictionaries.
        output_file (str): The path to the output JSON file.
    """
    if not reviews_data:
        logging.warning("No data provided to save.")
        return
    
    # Ensure the parent directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert datetime objects to ISO strings for JSON serialization
    for review in reviews_data:
        if 'at' in review and review['at']:
            review['at'] = review['at'].isoformat()
        if 'repliedAt' in review and review['repliedAt']:
            review['repliedAt'] = review['repliedAt'].isoformat()
            
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(reviews_data, f, ensure_ascii=False, indent=2)
        
    logging.info(f"Saved {len(reviews_data)} reviews to {output_file}")

if __name__ == "__main__":
    # When run directly, scrape a sample size
    data = scrape_play_store_reviews(count=200)
    save_reviews(data)
