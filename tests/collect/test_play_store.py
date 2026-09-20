import pytest
from unittest.mock import patch
from src.collect.play_store import scrape_play_store_reviews, save_reviews
import json
import datetime

@patch('src.collect.play_store.reviews')
def test_scrape_play_store_reviews_success(mock_reviews):
    """Test that the scraper correctly fetches and returns data from the google_play_scraper package."""
    # Mock the return value of google_play_scraper.reviews
    mock_data = [
        {"content": "Where did my photos go?", "score": 2, "at": datetime.datetime(2023, 1, 1)},
        {"content": "App keeps crashing on startup", "score": 1, "at": datetime.datetime(2023, 1, 2)}
    ]
    # reviews() returns a tuple: (result, continuation_token)
    mock_reviews.return_value = (mock_data, "mock_token")
    
    result = scrape_play_store_reviews(count=2)
    
    assert len(result) == 2
    assert result[0]['content'] == "Where did my photos go?"
    assert result[1]['score'] == 1
    mock_reviews.assert_called_once()

@patch('src.collect.play_store.reviews')
def test_scrape_play_store_reviews_error(mock_reviews):
    """Test that the scraper handles API errors gracefully without crashing."""
    mock_reviews.side_effect = Exception("API Rate Limit Reached")
    result = scrape_play_store_reviews()
    
    assert result == [] # Should return an empty list on failure

def test_save_reviews(tmp_path):
    """Test that the save function properly serializes datetime objects and saves JSON."""
    mock_reviews = [
        {"content": "Test review", "score": 4, "at": datetime.datetime(2023, 1, 1, 12, 0, 0)}
    ]
    
    # Use pytest's tmp_path fixture to avoid writing to real disk
    output_file = tmp_path / "data" / "raw" / "test_play_store.json"
    
    save_reviews(mock_reviews, str(output_file))
    
    assert output_file.exists()
    
    # Verify contents and datetime serialization
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    assert len(data) == 1
    assert data[0]['content'] == "Test review"
    assert data[0]['at'] == "2023-01-01T12:00:00"


@patch('src.collect.play_store.reviews')
def test_continuation_token_is_consumed(mock_reviews):
    mock_reviews.side_effect = [
        ([{'reviewId':str(i),'content':'Google Photos search'} for i in range(200)], 'next'),
        ([{'reviewId':'200','content':'Search is broken'}],None),
    ]
    result = scrape_play_store_reviews(count=201)
    assert len(result) == 201
    assert mock_reviews.call_args_list[1].kwargs['continuation_token'] == 'next'
