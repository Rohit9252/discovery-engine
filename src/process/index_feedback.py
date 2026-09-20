"""Refresh raw feedback search coverage without claiming AI extraction success."""
import json
from src.process.db import get_engine, get_session, ReviewExclusion
from src.process.source_audit import active_reviews
from src.process.vector_db import get_chroma_client, get_or_create_collection, add_documents


def index_rows(collection, rows, batch_size=100):
    for offset in range(0,len(rows),batch_size):
        batch = rows[offset:offset+batch_size]
        add_documents(collection,
            [f'Review: {row.text}' for row in batch],
            [{'source':row.source,'url':row.url or '', 'author':row.author or 'Anonymous',
              'failure_stage':'Not assessed','analysis_status':'raw_feedback'} for row in batch],
            [row.id for row in batch])
    return len(rows)


def main():
    engine = get_engine()
    collection = get_or_create_collection(get_chroma_client())
    with get_session(engine) as session:
        rows = active_reviews(session).order_by('id').all()
        excluded = [row.review_id for row in session.query(ReviewExclusion)]
        if excluded:
            collection.delete(ids=excluded)
        count = index_rows(collection,rows)
    engine.dispose()
    print(json.dumps({'active_feedback_indexed':count,'excluded_from_search':len(excluded),'collection_count':collection.count(),'analysis_status':'raw_feedback_only'}))


if __name__ == '__main__':
    main()
