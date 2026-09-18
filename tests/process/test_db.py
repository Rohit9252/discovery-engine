import pytest
from src.process.db import get_engine, init_db, get_session, ReviewMetadata
import datetime

def test_db_initialization_and_insertion(tmp_path):
    """
    Test that the SQLite database initializes correctly and can store/retrieve records.
    """
    # Use pytest's tmp_path fixture for an isolated temp database
    db_path = tmp_path / "test_reviews.db"
    engine = get_engine(str(db_path))
    
    # 1. Test Initialization
    init_db(engine)
    assert db_path.exists(), "Database file was not created"
    
    # 2. Test Insertion
    session = get_session(engine)
    new_review = ReviewMetadata(
        id="reddit_123",
        source="reddit",
        text="I hate losing my photos.",
        author="angry_user",
        created_at=datetime.datetime(2023, 1, 1),
        rating=None,
        url="https://reddit.com/r/googlephotos/123"
    )
    
    session.add(new_review)
    session.commit()
    
    # 3. Test Retrieval
    queried_review = session.query(ReviewMetadata).filter_by(id="reddit_123").first()
    
    assert queried_review is not None
    assert queried_review.text == "I hate losing my photos."
    assert queried_review.source == "reddit"
    assert queried_review.author == "angry_user"
