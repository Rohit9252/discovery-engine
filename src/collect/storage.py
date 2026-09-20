"""Preserve raw evidence with merged files, immutable snapshots, and receipts."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def record_key(row):
    return str(row.get('reviewId') or row.get('id') or hashlib.sha256(
        json.dumps(row, sort_keys=True, default=str).encode()).hexdigest())


def save_records(records, output_file):
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    merged = {record_key(row): row for row in existing}
    before = len(merged)
    for row in records:
        merged[record_key(row)] = row
    serialized = json.dumps(list(merged.values()), ensure_ascii=False, indent=2, default=lambda value: value.isoformat() if hasattr(value, 'isoformat') else str(value))
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(serialized, encoding='utf-8')
    temporary.replace(path)
    return {'previous': before, 'fetched': len(records), 'new_unique': len(merged) - before, 'merged': len(merged)}


def save_run(source, records, receipt, raw_dir):
    from src.process.paths import PROJECT_ROOT
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    folder = PROJECT_ROOT / 'data' / 'collection-runs' / run_id
    folder.mkdir(parents=True)
    (folder / f'{source}.json').write_text(json.dumps(records, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    filenames = {'reddit':'reddit_posts.json', 'play_store':'play_store_reviews.json', 'app_store':'app_store_reviews.json', 'youtube':'youtube_comments.json'}
    totals = save_records(records, Path(raw_dir) / filenames[source])
    result = {'source': source, 'run_id': run_id, 'pulled_at': datetime.now(timezone.utc).isoformat(), **receipt, **totals}
    (folder / 'receipt.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
