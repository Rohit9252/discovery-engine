import pytest
from unittest.mock import patch, MagicMock
from src.collect.app_store import scrape_app_store_reviews, save_reviews
import json
import datetime

@patch('src.collect.app_store.AppStore')
def test_scrape_app_store_reviews_success(MockAppStore):
    """Test that the scraper correctly fetches and returns data from the app_store_scraper package."""
    # Setup mock instance
    mock_instance = MockAppStore.return_value
    mock_instance.reviews = [
        {"review": "Hard to find old pics on my iPhone", "rating": 2, "date": datetime.datetime(2023, 1, 1)},
        {"content": "Face tagging is broken", "rating": 1, "date": datetime.datetime(2023, 1, 2)}
    ]
    
    result = scrape_app_store_reviews(count=2)
    
    assert len(result) == 2
    assert result[0]['review'] == "Hard to find old pics on my iPhone"
    mock_instance.review.assert_called_once_with(how_many=2)

@patch('src.collect.app_store.AppStore')
def test_scrape_app_store_reviews_error(MockAppStore):
    """Test that the scraper handles API errors gracefully without crashing."""
    MockAppStore.side_effect = Exception("Connection Error")
    result = scrape_app_store_reviews()
    
    assert result == [] # Should return an empty list on failure

def test_save_reviews(tmp_path):
    """Test that the save function properly serializes datetime objects and saves JSON."""
    mock_reviews = [
        {"review": "Test review", "rating": 4, "date": datetime.datetime(2023, 1, 1, 12, 0, 0)}
    ]
    
    output_file = tmp_path / "data" / "raw" / "test_app_store.json"
    
    save_reviews(mock_reviews, str(output_file))
    
    assert output_file.exists()
    
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    assert len(data) == 1
    assert data[0]['review'] == "Test review"
    assert data[0]['date'] == "2023-01-01T12:00:00"
