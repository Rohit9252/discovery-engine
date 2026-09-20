from unittest.mock import MagicMock, patch
import pytest
from src.collect.http_client import get_json, CollectionError
from src.collect.storage import save_records


@patch('src.collect.http_client.time.sleep')
@patch('src.collect.http_client.requests.get')
def test_retry_transient_http_failure(get, sleep):
    limited = MagicMock(status_code=429, headers={'Retry-After':'1'})
    success = MagicMock(status_code=200)
    success.json.return_value = {'data':[1]}
    get.side_effect = [limited, success]
    assert get_json('https://example.com') == {'data':[1]}
    sleep.assert_called_once_with(1)


@patch('src.collect.http_client.requests.get')
def test_errors_do_not_expose_keys(get):
    get.return_value = MagicMock(status_code=403)
    with pytest.raises(CollectionError, match='HTTP 403') as error:
        get_json('https://example.com', {'key':'secret'})
    assert 'secret' not in str(error.value)


def test_saving_empty_result_preserves_raw_data(tmp_path):
    path = tmp_path / 'raw.json'
    save_records([{'id':'one','text':'old'}],path)
    assert save_records([],path)['merged'] == 1
