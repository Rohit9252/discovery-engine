import sqlite3
from pathlib import Path

db_path = r'd:/Product Managment/Graduation Project/discovery-engine/data/processed/reviews.db'
if not Path(db_path).exists():
    print('DB not found!')
else:
    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    cursor.execute('SELECT count(*) FROM reviews_metadata WHERE id NOT IN (SELECT review_id FROM review_exclusions)')
    active_count = cursor.fetchone()[0]

    cursor.execute('SELECT status, count(*) FROM issue_analysis GROUP BY status')
    analyses = cursor.fetchall()

    print(f'Active records: {active_count}')
    print(f'Analyses counts: {analyses}')

    cursor.execute('SELECT error, count(*) FROM issue_analysis WHERE status="failed" GROUP BY error')
    errors = cursor.fetchall()
    print(f'Errors: {errors}')
    
    # Check research_runs
    cursor.execute('SELECT id, version, status, started_at, updated_at, error FROM research_runs ORDER BY started_at DESC LIMIT 1')
    run = cursor.fetchone()
    print(f'Latest Research Run: {run}')

pause_file = Path('d:/Product Managment/Graduation Project/discovery-engine/data/research/api-paused.json')
if pause_file.exists():
    print('API Pause file exists! Content:', pause_file.read_text())
else:
    print('API Pause file does NOT exist.')
