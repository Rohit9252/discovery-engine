import requests
from bs4 import BeautifulSoup
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_google_forums(limit=20):
    """
    Scrape recent questions from the Google Photos Support Community.
    Uses BeautifulSoup to parse the static HTML layout.
    """
    logging.info("Starting scraping for Google Photos Forums")
    url = "https://support.google.com/photos/threads?hl=en"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    all_threads = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find links containing '/photos/thread/' which represents a user question
        links = [a for a in soup.find_all('a', href=True) if '/photos/thread/' in a['href']]
            
        for link in links[:limit]:
            # Try to grab the title text, avoiding generic labels
            title = link.text.strip()
            if title:
                full_url = f"https://support.google.com{link['href']}" if link['href'].startswith('/') else link['href']
                all_threads.append({
                    'title': title,
                    'url': full_url
                })
                
    except Exception as e:
        logging.error(f"Error scraping Forums: {e}")
        
    logging.info(f"Scraped {len(all_threads)} forum threads.")
    return all_threads

def save_forum_posts(posts_data, output_file="data/raw/forums_posts.json"):
    """Save the scraped forum posts to a JSON file."""
    if not posts_data:
        logging.warning("No forum data to save.")
        return
        
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
            
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(posts_data, f, ensure_ascii=False, indent=2)
        
    logging.info(f"Saved {len(posts_data)} forum posts to {output_file}")

if __name__ == "__main__":
    data = scrape_google_forums()
    save_forum_posts(data)
