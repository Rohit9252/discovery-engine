import pytest
from unittest.mock import patch, MagicMock
from src.collect.reddit import scrape_reddit_posts, save_reddit_posts
import json

@patch('src.collect.reddit.requests.get')
@patch('src.collect.reddit.time.sleep') # mock sleep so tests run instantly
def test_scrape_reddit_posts_success(mock_sleep, mock_get):
    """Test that the scraper correctly fetches and parses the Reddit JSON response."""
    # Mock a successful JSON response matching Reddit's structure
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "abc123",
                        "title": "Search is broken",
                        "selftext": "I can't find anything.",
                        "score": 10,
                        "created_utc": 1672531200.0,
                        "permalink": "/r/googlephotos/comments/abc123/"
                    }
                }
            ]
        }
    }
    mock_get.return_value = mock_response
    
    result = scrape_reddit_posts(queries=["test"], limit=1)
    
    assert len(result) == 1
    assert result[0]['title'] == "Search is broken"
    assert result[0]['url'] == "https://www.reddit.com/r/googlephotos/comments/abc123/"
    mock_get.assert_called_once()
    mock_sleep.assert_called_once() # Ensure rate-limiting sleep is triggered

@patch('src.collect.reddit.requests.get')
def test_scrape_reddit_posts_error(mock_get):
    """Test that the scraper handles HTTP errors or rate limits without crashing."""
    mock_get.side_effect = Exception("HTTP 429 Too Many Requests")
    result = scrape_reddit_posts(queries=["test"])
    
    assert result == [] # Should safely return empty list

def test_save_reddit_posts(tmp_path):
    """Test that JSON saving works correctly."""
    mock_posts = [
        {"id": "abc", "title": "Test post"}
    ]
    
    output_file = tmp_path / "data" / "raw" / "test_reddit.json"
    save_reddit_posts(mock_posts, str(output_file))
    
    assert output_file.exists()
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    assert len(data) == 1
    assert data[0]['title'] == "Test post"
