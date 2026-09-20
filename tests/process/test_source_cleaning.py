from src.process.clean import clean_and_store_play_store, clean_and_store_app_store, clean_and_store_reddit
from src.process.db import get_engine, init_db, get_session, ReviewMetadata


def test_short_contextual_search_reviews_and_ios_are_retained(tmp_path):
    engine = get_engine(tmp_path / 'reviews.db')
    init_db(engine)
    with get_session(engine) as session:
        assert clean_and_store_play_store([{'reviewId':'p','content':'Search is broken','at':'2026-09-18'}],session) == 1
        assert clean_and_store_app_store([{'id':'i','review':'Cannot find old memories','date':'2026-09-18','rating':2}],session) == 1
        assert clean_and_store_app_store([{'id':'i','review':'Cannot find old memories','date':'2026-09-18','rating':2}],session) == 0
        assert session.query(ReviewMetadata).filter_by(source='app_store').one().rating == 2


def test_reddit_requires_google_photos_context(tmp_path):
    engine = get_engine(tmp_path / 'reviews.db')
    init_db(engine)
    with get_session(engine) as session:
        added = clean_and_store_reddit([
            {'id':'a','subreddit':'GooglePixel','text':'My Pixel camera glass is missing'},
            {'id':'b','subreddit':'googlephotos','text':'Search is broken'},
            {'id':'c','subreddit':'GooglePixel','text':'Google Photos search cannot find screenshots'},
        ],session)
        assert added == 2
        assert session.query(ReviewMetadata).filter_by(id='reddit_a').first() is None
