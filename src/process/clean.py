import pandas as pd
import json
import logging
from pathlib import Path
from src.process.db import get_engine, get_session, ReviewMetadata

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_and_store_play_store(raw_data, session):
    """Clean Play Store JSON data using Pandas and insert into SQLite."""
    if not raw_data:
        return 0
        
    df = pd.DataFrame(raw_data)
    
    # Standardize columns based on google-play-scraper output
    if 'reviewId' not in df.columns:
        logging.error("Invalid Play Store data format.")
        return 0
        
    df = df.rename(columns={
        'reviewId': 'id',
        'content': 'text',
        'score': 'rating',
        'userName': 'author',
        'at': 'created_at'
    })
    
    # Drop missing text and duplicates
    df = df.dropna(subset=['text'])
    df = df.drop_duplicates(subset=['id'])
    
    count = 0
    for _, row in df.iterrows():
        # Check if it already exists to avoid UniqueConstraint errors
        existing = session.query(ReviewMetadata).filter_by(id=row['id']).first()
        if not existing:
            created = pd.to_datetime(row['created_at']) if pd.notnull(row['created_at']) else None
            review = ReviewMetadata(
                id=str(row['id']),
                source='play_store',
                text=str(row['text']),
                author=str(row['author']) if pd.notnull(row['author']) else "Anonymous",
                rating=float(row['rating']) if pd.notnull(row['rating']) else None,
                created_at=created,
                url=None
            )
            session.add(review)
            count += 1
            
    session.commit()
    return count

def run_cleaning_pipeline(raw_dir="data/raw", db_path="data/processed/reviews.db"):
    """Run cleaning for all available raw JSON files and store in SQLite."""
    engine = get_engine(db_path)
    session = get_session(engine)
    
    # Process Play Store
    play_store_path = Path(raw_dir) / "play_store_reviews.json"
    if play_store_path.exists():
        logging.info("Processing Play Store reviews...")
        with open(play_store_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        added = clean_and_store_play_store(data, session)
        logging.info(f"Cleaned and stored {added} Play Store reviews.")
    else:
        logging.info("No Play Store data found to process.")

if __name__ == "__main__":
    run_cleaning_pipeline()
