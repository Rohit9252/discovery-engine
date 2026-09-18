import pytest
from unittest.mock import patch, MagicMock
from src.collect.forums import scrape_google_forums, save_forum_posts
import json

@patch('src.collect.forums.requests.get')
def test_scrape_forums_success(mock_get):
    """Test that BeautifulSoup correctly parses the Google Support HTML structure."""
    mock_response = MagicMock()
    mock_response.text = """
    <html>
        <body>
            <a href="/photos/thread/12345">Photos are missing from album</a>
        </body>
    </html>
    """
    mock_get.return_value = mock_response
    
    result = scrape_google_forums()
    
    assert len(result) == 1
    assert result[0]['title'] == "Photos are missing from album"
    assert result[0]['url'] == "https://support.google.com/photos/thread/12345"

@patch('src.collect.forums.requests.get')
def test_scrape_forums_error(mock_get):
    """Test that the scraper handles network errors gracefully."""
    mock_get.side_effect = Exception("Network Error")
    result = scrape_google_forums()
    
    assert result == []

def test_save_forum_posts(tmp_path):
    output_file = tmp_path / "data" / "raw" / "test_forums.json"
    save_forum_posts([{"title": "test"}], str(output_file))
    
    assert output_file.exists()
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert len(data) == 1
