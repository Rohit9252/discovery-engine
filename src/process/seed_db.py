import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.process.db import get_engine, get_session, ReviewMetadata, init_db
import datetime


def clear_mock_data():
    """Remove all seeded mock records (id starts with 'seed_') from the DB."""
    engine = get_engine()
    session = get_session(engine)
    deleted = session.query(ReviewMetadata).filter(
        ReviewMetadata.id.like("seed_%")
    ).delete(synchronize_session=False)
    session.commit()
    print(f"Cleared {deleted} mock seed records from the database.")
    return deleted


def seed_database():
    engine = get_engine()
    init_db(engine)
    session = get_session(engine)

    # Check if already seeded
    existing = session.query(ReviewMetadata).count()
    if existing > 0:
        print("Database already has records. Skipping seed.")
        return

    mock_reviews = [
        ("play_store", "I know I have a picture of my dog at the beach from 2019, but searching 'dog beach' just shows random sand photos. I have to scroll endlessly.", "user1"),
        ("app_store", "The new layout is confusing. I can't find the 'Locked Folder' anymore. Did they move it? I spent 20 minutes clicking around.", "user2"),
        ("reddit", "I took a photo of a receipt for a monitor I bought last month. Searching 'receipt' or 'monitor' brings up nothing. The OCR used to be good.", "user3"),
        ("forums", "BUG: When I try to backup my photos on cellular, it just pauses forever. I have to connect to WiFi even though cellular backup is enabled.", "user4"),
        ("play_store", "Face tagging is completely broken for my cat. It keeps grouping him with my neighbor's cat.", "user5"),
        ("reddit", "Workaround for finding old screenshots: type 'Screenshots' in the search bar, then add the year like '2022'. It kinda works but it's janky.", "user6"),
        ("forums", "I transferred my photos to my new iPhone and now half my albums are missing. The photos are there but the album structure is gone.", "user7"),
        ("play_store", "Editing videos on this app crashes it 90% of the time. I just want to trim a 10 second clip.", "user8"),
    ]

    count = 0
    for idx, (source, text, author) in enumerate(mock_reviews):
        review = ReviewMetadata(
            id=f"seed_{idx}",
            source=source,
            text=text,
            author=author,
            created_at=datetime.datetime.now(),
            rating=None,
            url=None
        )
        session.add(review)
        count += 1

    session.commit()
    print(f"Seeded {count} highly realistic test reviews into SQLite.")


if __name__ == "__main__":
    seed_database()
