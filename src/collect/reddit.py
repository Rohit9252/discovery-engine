import requests
import json
import logging
from pathlib import Path
import time

# Setup standard logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_reddit_posts(subreddit="googlephotos", queries=["find", "search", "bug", "issue"], limit=100):
    """
    Scrape recent posts from a subreddit using the public JSON API.
    
    Args:
        subreddit (str): The name of the subreddit.
        queries (list): List of search keywords to pull targeted complaints.
        limit (int): Maximum number of posts to fetch per query (max 100 per Reddit API).
        
    Returns:
        list: A list of dictionaries containing Reddit post data.
    """
    logging.info(f"Starting scraping for subreddit: r/{subreddit}")
    all_posts = []
    
    # Custom User-Agent is REQUIRED to bypass Reddit's public API blocks
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for query in queries:
        logging.info(f"Searching for keyword: '{query}'")
        url = f"https://www.reddit.com/r/{subreddit}/search.json?q={query}&restrict_sr=on&sort=new&limit={limit}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            children = data.get('data', {}).get('children', [])
            for child in children:
                post_data = child.get('data', {})
                extracted = {
                    'id': post_data.get('id'),
                    'title': post_data.get('title'),
                    'selftext': post_data.get('selftext'),
                    'score': post_data.get('score'),
                    'created_utc': post_data.get('created_utc'),
                    'url': f"https://www.reddit.com{post_data.get('permalink')}"
                }
                all_posts.append(extracted)
                
            # Be polite to the public API to avoid rate limits
            time.sleep(1.5)
            
        except Exception as e:
            logging.error(f"Error scraping Reddit for query '{query}': {e}")
            
    # Remove any potential duplicates if multiple queries caught the same post
    unique_posts = {post['id']: post for post in all_posts}.values()
    final_posts = list(unique_posts)
    
    logging.info(f"Successfully scraped {len(final_posts)} unique posts.")
    return final_posts

def save_reddit_posts(posts_data, output_file="data/raw/reddit_posts.json"):
    """
    Save the scraped Reddit posts to a JSON file.
    
    Args:
        posts_data (list): The list of post dictionaries.
        output_file (str): The path to the output JSON file.
    """
    if not posts_data:
        logging.warning("No data provided to save.")
        return
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
            
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(posts_data, f, ensure_ascii=False, indent=2)
        
    logging.info(f"Saved {len(posts_data)} posts to {output_file}")

if __name__ == "__main__":
    # When run directly, scrape the targeted queries
    data = scrape_reddit_posts()
    save_reddit_posts(data)
