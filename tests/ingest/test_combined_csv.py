"""Import boundaries and repeat-run safety for the combined CSV."""
import csv
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.ingest.combined_csv import import_rows


FIELDS = [
    'source', 'link', 'original_content', 'what_this_is', 'category', 'author',
    'posted_date', 'item_type', 'major_issue', 'stack_a1_tag', 'relevance',
    'helpful_count', 'rating', 'source_lane', 'notes', 'page_title', 'seed_file',
]


class CombinedImportTests(unittest.TestCase):
    def test_stages_only_positive_rows_and_imports_only_source_scoped_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, database = root / 'input.csv', root / 'reviews.db'
            rows = [
                self.row('Google Play Store', 'https://play.google.com/store/apps/details?id=com.google.android.apps.photos&reviewId=one', 'Search cannot find my old photos.'),
                self.row('Reddit (r/Cooking)', 'https://www.reddit.com/r/Cooking/comments/123/comment/', 'My soup recipe is gone.'),
                self.row('Google Photos Community', 'https://support.google.com/photos/thread/123', 'User reports a search issue.', item_type='seed_paraphrase'),
                self.row('YouTube', 'https://www.youtube.com/watch?v=one&lc=two', 'Ask Photos returns the wrong image.', page_title='Google Photos search'),
                self.row('Google Play Store', 'https://play.google.com/store/apps/details?id=com.google.android.apps.photos&reviewId=two', 'Unrelated review.', relevance='low'),
            ]
            with path.open('w', encoding='utf-8', newline='') as output:
                writer = csv.DictWriter(output, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute('CREATE TABLE reviews_metadata (id TEXT PRIMARY KEY, source TEXT, text TEXT, author TEXT, created_at TEXT, rating REAL, url TEXT)')
                connection.execute('INSERT INTO reviews_metadata (id, source, text) VALUES (?, ?, ?)', ('prior', 'play_store', 'Search cannot find my old photos.'))
            result = import_rows(path, database)
            self.assertEqual(result['positive_source_rows'], 4)
            self.assertEqual(result['existing'], 1)
            self.assertEqual(result['held'], 2)
            self.assertEqual(result['imported'], 1)
            self.assertEqual(result['ledger_total'], 4)
            self.assertEqual(result['review_total'], 2)
            self.assertEqual(import_rows(path, database)['already_staged'], 4)
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM csv_import_ledger WHERE reason='product_scope_unconfirmed'").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT count(*) FROM csv_import_ledger WHERE reason='derived_or_secondary'").fetchone()[0], 1)

    @staticmethod
    def row(source, link, content, item_type='play_review', relevance='high', page_title=''):
        row = dict.fromkeys(FIELDS, '')
        row.update(source=source, link=link, original_content=content,
                   item_type=item_type, relevance=relevance, page_title=page_title,
                   category='search_wrong_results')
        return row


if __name__ == '__main__':
    unittest.main()
