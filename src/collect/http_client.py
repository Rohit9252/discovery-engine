"""Bounded public API requests that never log credential-bearing URLs."""
import time
import requests


class CollectionError(RuntimeError):
    pass


def get_json(url, params=None, attempts=3, timeout=15):
    for attempt in range(attempts):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            status = response.status_code
            if status == 200:
                return response.json()
            retryable = status in (429, 500, 502, 503, 504)
            if status == 422:
                retryable = 'timeout' in response.text.lower()
            if not retryable:
                raise CollectionError(f'HTTP {status}')
            delay = min(30, 2 ** attempt)
            retry_after = response.headers.get('Retry-After', '')
            if str(retry_after).isdigit():
                delay = min(30, int(retry_after))
        except (requests.RequestException, ValueError) as exc:
            delay = min(30, 2 ** attempt)
            failure = type(exc).__name__
        else:
            failure = f'HTTP {status}'
        if attempt + 1 < attempts:
            time.sleep(delay)
    raise CollectionError(f'Request failed after {attempts} attempts ({failure})')
