"""Import every Phase 1 CSV row while retaining its evidence type."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

import pandas as pd

from src.ingest.combined_csv import (DERIVED, canonical_source, create_ledger,
                                     normalized, parse_date, product_scoped, row_id)
from src.process.db import get_engine, init_db
from src.process.paths import PROJECT_ROOT


CATALOG_PATH = PROJECT_ROOT.parent / 'preprocessing' / 'discovery-engine' / 'phase1_discovery_web_expanded_3000.csv'
STAGING_DB_PATH = PROJECT_ROOT / 'data' / 'processed' / 'reviews-phase1-build.db'
REQUIRED_COLUMNS = {
    'source', 'link', 'original_content', 'category', 'item_type', 'relevance',
    'ChatGPT_Record_Type', 'author', 'posted_date', 'rating', 'page_title',
}
SOURCE_RECORD_TYPE = 'existing_in_scope_evidence'


def read_catalog(path):
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f'Catalog missing required columns: {sorted(missing)}')
    if frame.empty:
        raise ValueError('Catalog contains no rows')
    return frame.to_dict(orient='records')


def catalog_disposition(row):
    record_type = row['ChatGPT_Record_Type'].strip()
    if record_type == 'web_grounded_scenario' or row['item_type'] == 'derived_scenario':
        return 'held', 'synthetic_scenario'
    if record_type == 'web_atomic_evidence':
        return 'held', 'paraphrased_web_evidence'
    if record_type != SOURCE_RECORD_TYPE:
        return 'held', 'unknown_record_type'
    if row['item_type'] in DERIVED:
        return 'held', 'derived_or_secondary'
    if not row['original_content'].strip():
        return 'held', 'missing_source_text'
    if not row['link'].startswith(('https://', 'http://')):
        return 'held', 'missing_source_url'
    if not product_scoped(row):
        return 'held', 'product_scope_unconfirmed'
    return 'candidate', 'source_scoped'


def import_catalog(path=CATALOG_PATH, db_path=STAGING_DB_PATH):
    """Stage every row for analysis; retain the older review table during transition."""
    path, db_path = Path(path).resolve(), Path(db_path).resolve()
    rows = read_catalog(path)
    engine = get_engine(db_path)
    try:
        init_db(engine)
    finally:
        engine.dispose()
    counts = Counter()
    connection = sqlite3.connect(db_path)
    try:
        connection.execute('PRAGMA busy_timeout=30000')
        with connection:
            create_ledger(connection)
            connection.execute('UPDATE phase1_catalog_rows SET active=0 WHERE source_file=?',
                               (path.name,))
            existing = {
                (source, normalized(text)): review_id
                for review_id, source, text in connection.execute(
                    'SELECT id, source, text FROM reviews_metadata')
            }
            for number, row in enumerate(rows, start=1):
                raw_json = json.dumps(row, ensure_ascii=False, sort_keys=True)
                content_hash = hashlib.sha256(raw_json.encode('utf-8')).hexdigest()
                connection.execute('''INSERT INTO phase1_catalog_rows
                    (id, row_number, source_file, source_type, source, url, text, raw_json,
                     content_hash, active, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
                    ON CONFLICT(id) DO UPDATE SET
                        row_number=excluded.row_number, source_file=excluded.source_file,
                        source_type=excluded.source_type, source=excluded.source,
                        url=excluded.url, text=excluded.text, raw_json=excluded.raw_json,
                        content_hash=excluded.content_hash, active=1,
                        imported_at=excluded.imported_at''',
                    (f'phase1_{number:05d}', number, path.name, row['ChatGPT_Record_Type'],
                     row['source'], row['link'], row['original_content'], raw_json, content_hash))
                identifier = row_id(row)
                if connection.execute('SELECT 1 FROM csv_import_ledger WHERE row_id=?',
                                      (identifier,)).fetchone():
                    counts['already_staged'] += 1
                    continue
                status, reason = catalog_disposition(row)
                source = canonical_source(row['source'])
                review_id = None
                if status == 'candidate':
                    key = (source, normalized(row['original_content']))
                    review_id = existing.get(key)
                    if review_id:
                        status, reason = 'existing', 'matching_source_text'
                    else:
                        review_id = f'csv_{identifier[:24]}'
                        try:
                            rating = float(row['rating']) if row['rating'].strip() else None
                        except ValueError:
                            rating = None
                        connection.execute('''INSERT INTO reviews_metadata
                            (id, source, text, author, created_at, rating, url)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            (review_id, source, row['original_content'], row['author'] or None,
                             parse_date(row['posted_date']), rating, row['link']))
                        existing[key] = review_id
                        status = 'imported'
                connection.execute('''INSERT INTO csv_import_ledger
                    (row_id, source_file, source, url, original_content, manual_relevance,
                     manual_category, item_type, disposition, reason, review_id, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
                    (identifier, path.name, row['source'], row['link'], row['original_content'],
                     row['relevance'], row['category'], row['item_type'], status, reason, review_id))
                counts[status] += 1
        counts['catalog_rows'] = len(rows)
        counts['active_catalog_rows'] = connection.execute(
            'SELECT count(*) FROM phase1_catalog_rows WHERE active=1 AND source_file=?',
            (path.name,)).fetchone()[0]
        counts['ledger_rows'] = connection.execute('SELECT count(*) FROM csv_import_ledger').fetchone()[0]
        counts['active_reviews'] = connection.execute('SELECT count(*) FROM reviews_metadata').fetchone()[0]
        counts['held_by_reason'] = dict(connection.execute(
            "SELECT reason, count(*) FROM csv_import_ledger WHERE disposition='held' GROUP BY reason"))
        if counts['active_catalog_rows'] != len(rows):
            raise ValueError('Active catalog rows and CSV do not reconcile')
        return dict(counts)
    finally:
        connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=CATALOG_PATH)
    parser.add_argument('--db', type=Path, default=STAGING_DB_PATH)
    args = parser.parse_args()
    print(json.dumps(import_catalog(args.csv, args.db), indent=2))
