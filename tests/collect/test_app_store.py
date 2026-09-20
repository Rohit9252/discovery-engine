from unittest.mock import patch
from src.collect.app_store import scrape_via_rss, normalize, save_reviews


@patch('src.collect.app_store.time.sleep')
@patch('src.collect.app_store.get_json')
def test_rss_pagination_preserves_ids(get_json, sleep):
    row = {'id':{'label':'123'}, 'im:rating':{'label':'2'}, 'content':{'label':'Cannot find old photos'}, 'title':{'label':'Search'}, 'updated':{'label':'2026-09-18'}}
    get_json.side_effect = [{'feed':{'entry':[row]}},{'feed':{'entry':[]}}]
    records = normalize(scrape_via_rss(pages=2), 'rss')
    assert records[0]['id'] == '123'
    assert records[0]['app_id'] == 962194608
    assert records[0]['url_scope'] == 'app_page'
    assert get_json.call_count == 2


def test_library_ids_are_content_stable():
    rows = [{'review':'Cannot find old photos','date':'2026-09-18'}]
    assert normalize(rows, 'library')[0]['id'] == normalize(rows, 'library')[0]['id']


def test_save_merges_without_losing_previous_records(tmp_path):
    path = tmp_path / 'apple.json'
    save_reviews([{'id':'a','review':'One'}], path)
    result = save_reviews([{'id':'b','review':'Two'}], path)
    assert result['merged'] == 2
