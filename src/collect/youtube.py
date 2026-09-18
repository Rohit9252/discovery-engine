import requests
import json
import logging
import os
from pathlib import Path

# Setup standard logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_youtube_comments(api_key, video_ids, max_results=100):
    """
    Fetch top-level comments for a list of YouTube videos.
    
    Args:
        api_key (str): YouTube Data API v3 Key.
        video_ids (list): List of YouTube video IDs.
        max_results (int): Max comments to pull per video.
        
    Returns:
        list: List of dictionaries containing comment data.
    """
    all_comments = []
    
    for video_id in video_ids:
        logging.info(f"Fetching comments for video: {video_id}")
        url = f"https://www.googleapis.com/youtube/v3/commentThreads?key={api_key}&textFormat=plainText&part=snippet&videoId={video_id}&maxResults={max_results}"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                logging.error(f"YouTube API Error for {video_id}: {response.text}")
                continue
                
            data = response.json()
            for item in data.get('items', []):
                comment = item['snippet']['topLevelComment']['snippet']
                all_comments.append({
                    'id': item['id'],
                    'video_id': video_id,
                    'author': comment.get('authorDisplayName'),
                    'text': comment.get('textDisplay'),
                    'like_count': comment.get('likeCount'),
                    'published_at': comment.get('publishedAt')
                })
        except Exception as e:
            logging.error(f"Error fetching comments for {video_id}: {e}")
            
    logging.info(f"Scraped {len(all_comments)} YouTube comments.")
    return all_comments

def save_youtube_comments(comments, output_file="data/raw/youtube_comments.json"):
    """Save the scraped comments to a JSON file."""
    if not comments:
        logging.warning("No YouTube data to save.")
        return
        
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
            
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)
        
    logging.info(f"Saved {len(comments)} comments to {output_file}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("YOUTUBE_API_KEY")
    if api_key:
        # Targeting popular Google Photos tutorial/review videos
        target_videos = ["G_P4a41i_eM", "p_Y-Z8P_350", "Y3XhF9G7l9M"]
        data = get_youtube_comments(api_key, target_videos)
        save_youtube_comments(data)
    else:
        logging.error("YOUTUBE_API_KEY not found in environment.")
