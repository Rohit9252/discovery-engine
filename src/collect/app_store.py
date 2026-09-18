from app_store_scraper import AppStore
import json
import logging
from pathlib import Path

# Setup standard logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_app_store_reviews(app_name="google-photos", app_id=962194608, country='us', count=1000):
    """
    Scrape recent reviews from the Apple App Store.
    
    Args:
        app_name (str): The name of the app on the App Store.
        app_id (int): The Apple App Store ID for Google Photos.
        country (str): Country code.
        count (int): Number of reviews to fetch.
        
    Returns:
        list: A list of dictionaries containing review data.
    """
    logging.info(f"Starting scraping for App Store app: {app_name} (Target: {count} reviews)")
    try:
        app = AppStore(country=country, app_name=app_name, app_id=app_id)
        app.review(how_many=count)
        
        logging.info(f"Successfully scraped {len(app.reviews)} reviews.")
        return app.reviews
    except Exception as e:
        logging.error(f"Error scraping App Store: {e}")
        return []

def save_reviews(reviews_data, output_file="data/raw/app_store_reviews.json"):
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
        if 'date' in review and review['date']:
            review['date'] = review['date'].isoformat()
            
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(reviews_data, f, ensure_ascii=False, indent=2)
        
    logging.info(f"Saved {len(reviews_data)} reviews to {output_file}")

if __name__ == "__main__":
    # When run directly, scrape a sample size
    data = scrape_app_store_reviews(count=200)
    save_reviews(data)
