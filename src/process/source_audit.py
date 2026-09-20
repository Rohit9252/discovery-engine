"""Quarantine known historical context gaps without deleting feedback."""
import json
from src.collect.config import mentions_product
from src.process.db import ReviewMetadata, ReviewExclusion, get_engine, get_session, init_db
from src.process.paths import PROJECT_ROOT


def active_reviews(session):
    return session.query(ReviewMetadata).filter(
        ~ReviewMetadata.id.in_(session.query(ReviewExclusion.review_id)))


def audit_reddit_context():
    engine = get_engine()
    init_db(engine)
    rows = json.loads((PROJECT_ROOT / 'data/raw/reddit_posts.json').read_text(encoding='utf-8'))
    quarantined = []
    with get_session(engine) as session:
        stored = {row.id for row in session.query(ReviewMetadata).filter_by(source='reddit')}
        for row in rows:
            key = 'reddit_' + str(row.get('id'))
            if key not in stored:
                continue
            context = str(row.get('text') or '') + ' ' + str(row.get('context_title') or '')
            confirmed = (str(row.get('subreddit','')).lower() == 'googlephotos'
                         or row.get('product_context_verified') is True or mentions_product(context))
            if not confirmed:
                reason = 'Historical Reddit record outside r/googlephotos lacks explicit Google Photos context; excluded pending review.'
                session.merge(ReviewExclusion(review_id=key,reason=reason))
                quarantined.append({'id':key,'subreddit':row.get('subreddit'),'reason':reason})
        session.commit()
        report = {'stored':session.query(ReviewMetadata).count(),'active':active_reviews(session).count(),'excluded_count':len(quarantined),'excluded':quarantined}
    engine.dispose()
    target = PROJECT_ROOT / 'data/collection-runs/source-audit.json'
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__ == '__main__':
    report = audit_reddit_context()
    print(json.dumps({key:report[key] for key in ('stored','active','excluded_count')}))
