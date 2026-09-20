import pytest
from src.process.clean import clean_and_store_play_store
from src.process.db import get_engine, init_db, get_session, ReviewMetadata

def test_clean_and_store_play_store(tmp_path):
    """Test that the pandas cleaning script correctly deduplicates and maps columns."""
    # Setup isolated test DB
    db_path = tmp_path / "test_clean.db"
    engine = get_engine(str(db_path))
    init_db(engine)
    session = get_session(engine)
    
    # Mock raw JSON data with typical scraping issues
    raw_data = [
        {"reviewId": "1", "content": "Great app for my daily photos", "score": 5, "userName": "User A", "at": "2023-01-01T00:00:00"},
        {"reviewId": "2", "content": "Keeps crashing", "score": 1, "userName": "User B", "at": "2023-01-02T00:00:00"},
        {"reviewId": "1", "content": "Great app for my daily photos", "score": 5, "userName": "User A", "at": "2023-01-01T00:00:00"}, # Duplicate ID
        {"reviewId": "3", "content": None, "score": 3, "userName": "User C", "at": "2023-01-03T00:00:00"}, # Missing text
    ]
    
    added = clean_and_store_play_store(raw_data, session)
    
    # The pipeline should deduplicate ID '1' and drop ID '3' due to missing text
    assert added == 2
    
    # Verify DB insertion
    saved_reviews = session.query(ReviewMetadata).all()
    assert len(saved_reviews) == 2
    
    # Verify column mapping logic
    review1 = session.query(ReviewMetadata).filter_by(id="1").first()
    assert review1.text == "Great app for my daily photos"
    assert review1.rating == 5.0
    assert review1.source == "play_store"
    assert review1.author == "User A"
