from unittest.mock import patch
import pytest
from src.collect.reddit import scrape_posts_by_keyword, scrape_comments_from_threads


@patch('src.collect.reddit.time.sleep')
@patch('src.collect.reddit.get_json')
def test_body_search_context_and_pagination(get_json, sleep):
    get_json.side_effect = [
        {'data':[{'id':'a','title':'Help please','selftext':'Google Photos search cannot find the receipt','created_utc':20}, {'id':'b','title':'Where to find a Pixel charger','created_utc':19}]},
        {'data':[{'id':'c','title':'Ask Photos finds old memories','created_utc':10}]},
    ]
    rows = scrape_posts_by_keyword(subreddits=['GooglePixel'], limit=2, pages=2)
    assert set(rows) == {'a','c'}
    assert get_json.call_args_list[1].args[1]['before'] == 19


def test_comments_reject_unverified_historical_ids():
    with pytest.raises(ValueError):
        scrape_comments_from_threads(['1dqw3p4'])


@patch('src.collect.reddit.get_json')
def test_comment_uses_exact_link_and_parent_context(get_json):
    get_json.return_value = {'data':[{'id':'c','body':'Search does not work','created_utc':10}]}
    result = scrape_comments_from_threads([{'id':'p','title':'Ask Photos search','subreddit':'googlephotos','product_context_verified':True}])
    assert result['comment_c']['url'].endswith('/p/_/c/')
    assert result['comment_c']['context_title'] == 'Ask Photos search'
