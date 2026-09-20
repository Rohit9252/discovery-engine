"""Stage the 1,813 positive-label CSV rows and import source-scoped candidates.

Run from the discovery-engine directory with ``python -m src.ingest.combined_csv``.
The source CSV is read only. The ledger records every positive-label decision.
"""
import argparse
import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


CSV_PATH = Path(__file__).resolve().parents[3] / 'data' / 'structured-evidence-ALL-COMBINED.csv'
DB_PATH = Path(__file__).resolve().parents[2] / 'data' / 'processed' / 'reviews.db'
POSITIVE = {'high', 'medium', 'retrieval_relevant'}
DERIVED = {
    'seed_paraphrase', 'theme_summary', 'discovery_case',
    'ceo_discovery_case', 'research_excerpt', 'press_article',
    'youtube_description',
}
REQUIRED = {'source', 'link', 'original_content', 'category', 'item_type', 'relevance'}


def normalized(text):
    return re.sub(r'\s+', ' ', (text or '').strip()).casefold()


def canonical_source(source):
    value = source.lower()
    if value == 'google play store':
        return 'play_store'
    if value == 'apple app store':
        return 'app_store'
    if value == 'youtube':
        return 'youtube'
    if 'reddit' in value or value.startswith('r/'):
        return 'reddit'
    if value == 'google photos community':
        return 'google_photos_community'
    return 'web_forum'


def product_scoped(row):
    source = row['source'].lower()
    url = row['link'].lower()
    text = row['original_content'].lower()
    title = row['page_title'].lower()
    if source == 'google play store':
        return 'play.google.com/store/apps/details' in url and 'com.google.android.apps.photos' in url
    if source == 'apple app store':
        return ('apps.apple.com/' in url or 'itunes.apple.com/' in url) and '962194608' in url
    if source == 'google photos community':
        return 'support.google.com/photos/thread/' in url
    if 'reddit' in source or source.startswith('r/'):
        return '/r/googlephotos/' in url or 'google photos' in text or 'ask photos' in text
    if source == 'youtube':
        return ('google photos' in title or 'ask photos' in title or
                'google photos' in text or 'ask photos' in text)
    return 'google photos' in text or 'ask photos' in text


def disposition(row):
    if row['item_type'] in DERIVED:
        return 'held', 'derived_or_secondary'
    if not row['link'].startswith(('https://', 'http://')):
        return 'held', 'missing_source_url'
    if not row['original_content'].strip():
        return 'held', 'missing_source_text'
    if not product_scoped(row):
        return 'held', 'product_scope_unconfirmed'
    return 'candidate', 'source_scoped'


def row_id(row):
    key = '\n'.join((row['source'], row['link'], row['original_content']))
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


def parse_date(value):
    value = value.strip()
    for fmt in ('%Y-%m-%d', '%b %d, %Y', '%B %d, %Y', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).isoformat(sep=' ')
        except ValueError:
            continue
    return None


def read_positive(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f'Missing required columns: {sorted(missing)}')
        rows = list(reader)
    positive = [row for row in rows if row['relevance'].strip() in POSITIVE]
    if path.resolve() == CSV_PATH.resolve() and (len(rows), len(positive)) != (2979, 1813):
        raise ValueError(f'Combined CSV changed: {len(rows)} total and {len(positive)} positive rows')
    return positive


def create_ledger(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS csv_import_ledger (
        row_id TEXT PRIMARY KEY,
        source_file TEXT NOT NULL,
        source TEXT NOT NULL,
        url TEXT NOT NULL,
        original_content TEXT NOT NULL,
        manual_relevance TEXT NOT NULL,
        manual_category TEXT NOT NULL,
        item_type TEXT NOT NULL,
        disposition TEXT NOT NULL,
        reason TEXT NOT NULL,
        review_id TEXT,
        imported_at TEXT NOT NULL
    )''')
    connection.execute('CREATE INDEX IF NOT EXISTS ix_csv_import_ledger_review_id ON csv_import_ledger(review_id)')


def import_rows(path=CSV_PATH, db_path=DB_PATH):
    rows = read_positive(Path(path))
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f'Existing review database missing: {db_path}')
    connection = sqlite3.connect(db_path)
    try:
        connection.execute('PRAGMA busy_timeout=30000')
        with connection:
            create_ledger(connection)
            existing = {
                (source, normalized(text)): review_id
                for review_id, source, text in connection.execute('SELECT id, source, text FROM reviews_metadata')
            }
            counts = Counter()
            for row in rows:
                identifier = row_id(row)
                prior = connection.execute('SELECT disposition FROM csv_import_ledger WHERE row_id=?', (identifier,)).fetchone()
                if prior:
                    counts['already_staged'] += 1
                    continue
                status, reason = disposition(row)
                review_id = None
                source = canonical_source(row['source'])
                if status == 'candidate':
                    key = (source, normalized(row['original_content']))
                    if key in existing:
                        status, reason, review_id = 'existing', 'matching_source_text', existing[key]
                    else:
                        review_id = f'csv_{identifier[:24]}'
                        rating = row['rating'].strip()
                        try:
                            rating = float(rating) if rating else None
                        except ValueError:
                            rating = None
                        connection.execute('''INSERT INTO reviews_metadata
                            (id, source, text, author, created_at, rating, url)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (review_id, source, row['original_content'], row['author'] or None,
                             parse_date(row['posted_date']), rating, row['link']))
                        existing[key] = review_id
                        status, reason = 'imported', 'source_scoped'
                connection.execute('''INSERT INTO csv_import_ledger
                    (row_id, source_file, source, url, original_content,
                     manual_relevance, manual_category, item_type, disposition,
                     reason, review_id, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (identifier, Path(path).name, row['source'], row['link'], row['original_content'],
                     row['relevance'], row['category'], row['item_type'], status, reason,
                     review_id, datetime.now(timezone.utc).isoformat()))
                counts[status] += 1
        counts['positive_source_rows'] = len(rows)
        counts['ledger_total'] = connection.execute('SELECT count(*) FROM csv_import_ledger').fetchone()[0]
        counts['review_total'] = connection.execute('SELECT count(*) FROM reviews_metadata').fetchone()[0]
        return dict(counts)
    finally:
        connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=CSV_PATH)
    parser.add_argument('--db', type=Path, default=DB_PATH)
    args = parser.parse_args()
    print(json.dumps(import_rows(args.csv, args.db), indent=2))
