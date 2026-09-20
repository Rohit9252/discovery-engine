import pytest
from unittest.mock import patch, MagicMock
from src.collect.youtube import get_youtube_comments, save_youtube_comments
import json

@patch('src.collect.http_client.requests.get')
def test_get_youtube_comments_success(mock_get):
    """Test that the scraper correctly parses the YouTube API JSON response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {
                "id": "comment123",
                "snippet": {
                    "topLevelComment": {
                        "snippet": {
                            "authorDisplayName": "TestUser",
                            "textDisplay": "How do I find baby pictures?",
                            "likeCount": 5,
                            "publishedAt": "2023-01-01T00:00:00Z"
                        }
                    }
                }
            }
        ]
    }
    mock_get.return_value = mock_response
    
    result = get_youtube_comments("fake_key", ["fake_vid"])
    
    assert len(result) == 1
    assert result[0]['text'] == "How do I find baby pictures?"
    assert result[0]['author'] == "TestUser"
    mock_get.assert_called_once()

@patch('src.collect.http_client.requests.get')
def test_get_youtube_comments_error(mock_get):
    """Test that the scraper handles API quota/HTTP errors gracefully."""
    mock_response = MagicMock()
    mock_response.status_code = 403 # Quota exceeded
    mock_get.return_value = mock_response
    
    result = get_youtube_comments("fake_key", ["fake_vid"])
    assert result == []

def test_save_youtube_comments(tmp_path):
    output_file = tmp_path / "data" / "raw" / "test_youtube.json"
    save_youtube_comments([{"text": "test"}], str(output_file))
    
    assert output_file.exists()
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert len(data) == 1


@patch('src.collect.youtube.get_json')
def test_pagination_and_exact_comment_ids(mock_json):
    mock_json.side_effect = [
        {'items':[{'id':'thread','snippet':{'topLevelComment':{'id':'comment','snippet':{'textOriginal':'Search is broken'}}}}], 'nextPageToken':'next'},
        {'items':[]},
    ]
    result = get_youtube_comments('fake_key',['video'],verified_titles={'video':'Google Photos search'})
    assert mock_json.call_args_list[1].args[1]['pageToken'] == 'next'
    assert result[0]['url'].endswith('&lc=comment')
    assert result[0]['product_context_verified']


@patch('src.collect.youtube.get_json')
def test_unrelated_video_metadata_is_rejected(mock_json):
    from src.collect.youtube import verify_videos
    mock_json.return_value = {'items':[{'id':'wrong','snippet':{'title':'Pixel battery review'}}, {'id':'right','snippet':{'title':'Google Photos search tutorial'}}]}
    assert verify_videos('fake_key',['wrong','right']) == {'right':'Google Photos search tutorial'}
