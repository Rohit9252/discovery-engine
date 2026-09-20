import csv
import sqlite3

from src.ingest.phase1_catalog import import_catalog


FIELDS = ['source', 'link', 'original_content', 'category', 'item_type', 'relevance',
          'ChatGPT_Record_Type', 'author', 'posted_date', 'rating', 'page_title']


def row(text, record_type='existing_in_scope_evidence', item_type='community_original_post',
        link='https://support.google.com/photos/thread/123/search', source='Google Photos Community'):
    return dict(source=source, link=link, original_content=text, category='search_zero_results',
                item_type=item_type, relevance='high', ChatGPT_Record_Type=record_type,
                author='User', posted_date='Sep 20, 2026', rating='', page_title='Google Photos search')


def test_catalog_import_separates_source_reports_and_reconciles_all_rows(tmp_path):
    path, db_path = tmp_path / 'catalog.csv', tmp_path / 'new.db'
    rows = [
        row('I searched for my old dog photo and found nothing.'),
        row('I searched for my old dog photo and found nothing.',
            link='https://support.google.com/photos/thread/456/search'),
        row('Web-grounded discovery scenario: search for a dog photo.',
            record_type='web_grounded_scenario', item_type='derived_scenario'),
        row('User search failed.', record_type='web_atomic_evidence', item_type='web_atomic_evidence'),
        row('I cannot find my camera photo.', source='Reddit',
            link='https://reddit.com/r/unrelated/comments/123'),
    ]
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    result = import_catalog(path, db_path)
    assert result['catalog_rows'] == result['ledger_rows'] == 5
    assert result['active_catalog_rows'] == 5
    assert result['active_reviews'] == 1
    assert result['held_by_reason'] == {
        'paraphrased_web_evidence': 1, 'product_scope_unconfirmed': 1,
        'synthetic_scenario': 1,
    }
    with sqlite3.connect(db_path) as connection:
        assert connection.execute('SELECT count(*) FROM reviews_metadata').fetchone()[0] == 1
        assert connection.execute('SELECT count(*) FROM phase1_catalog_rows WHERE active=1').fetchone()[0] == 5
        assert dict(connection.execute('SELECT source_type, count(*) FROM phase1_catalog_rows GROUP BY source_type')) == {
            'existing_in_scope_evidence': 3, 'web_atomic_evidence': 1, 'web_grounded_scenario': 1}
        assert connection.execute("SELECT count(*) FROM csv_import_ledger WHERE disposition='held'").fetchone()[0] == 3
    repeated = import_catalog(path, db_path)
    assert repeated['already_staged'] == 5 and repeated['active_reviews'] == 1
    assert repeated['active_catalog_rows'] == 5

    rows[2]['original_content'] = 'Web-grounded scenario: find an old dog photo by place.'
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    changed = import_catalog(path, db_path)
    assert changed['active_catalog_rows'] == 5
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            'SELECT text FROM phase1_catalog_rows WHERE id=?', ('phase1_00003',)
        ).fetchone()[0] == rows[2]['original_content']
