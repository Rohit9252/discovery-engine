"""
Data cleaning pipeline for the Google Photos Discovery Engine.

Reads raw JSON files from data/raw/, normalizes each source into the
unified ReviewMetadata schema, deduplicates, and inserts into SQLite.

Supported sources:
    - Play Store  (data/raw/play_store_reviews.json)
    - YouTube     (data/raw/youtube_comments.json)
    - Reddit      (data/raw/reddit_posts.json)

Usage:
    uv run python src/process/clean.py
"""

import hashlib
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path so we can import 'src'
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd

from src.process.db import ReviewMetadata, get_engine, get_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Minimum text length to be considered a usable review
MIN_TEXT_LENGTH = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stable_id(prefix: str, *parts: str) -> str:
    """Generate a stable, collision-resistant ID from arbitrary string parts."""
    payload = "|".join(str(p) for p in parts)
    return prefix + "_" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def _upsert(session, review: ReviewMetadata) -> bool:
    """Insert a review only if its ID does not already exist. Returns True if inserted."""
    existing = session.query(ReviewMetadata).filter_by(id=review.id).first()
    if existing:
        return False
    session.add(review)
    return True


# ---------------------------------------------------------------------------
# Source 1: Play Store
# ---------------------------------------------------------------------------

def clean_and_store_play_store(raw_data: list[dict], session) -> int:
    """
    Parse google-play-scraper output and insert into SQLite.
    Fields: reviewId, content, score, userName, at
    """
    if not raw_data:
        logging.warning("Play Store: no raw data provided.")
        return 0

    df = pd.DataFrame(raw_data)

    if "reviewId" not in df.columns:
        logging.error("Play Store: invalid data format - missing 'reviewId' column.")
        return 0

    df = df.rename(columns={
        "reviewId": "id",
        "content":  "text",
        "score":    "rating",
        "userName": "author",
        "at":       "created_at",
    })

    df = df.dropna(subset=["text"])
    df = df[df["text"].str.len() >= MIN_TEXT_LENGTH]
    df = df.drop_duplicates(subset=["id"])

    count = 0
    for _, row in df.iterrows():
        created = pd.to_datetime(row["created_at"]) if pd.notnull(row.get("created_at")) else None
        review = ReviewMetadata(
            id=str(row["id"]),
            source="play_store",
            text=str(row["text"]),
            author=str(row["author"]) if pd.notnull(row.get("author")) else "Anonymous",
            rating=float(row["rating"]) if pd.notnull(row.get("rating")) else None,
            created_at=created,
            url=None,
        )
        if _upsert(session, review):
            count += 1

    session.commit()
    logging.info("Play Store: inserted %d new records.", count)
    return count


# ---------------------------------------------------------------------------
# Source 2: YouTube
# ---------------------------------------------------------------------------

def clean_and_store_youtube(raw_data: list[dict], session) -> int:
    """
    Parse YouTube Data API comment output and insert into SQLite.
    Fields: id, video_id, author, text, like_count, published_at
    """
    if not raw_data:
        logging.warning("YouTube: no raw data provided.")
        return 0

    count = 0
    for item in raw_data:
        text = (item.get("text") or "").strip()
        if len(text) < MIN_TEXT_LENGTH:
            continue

        # Filter out purely promotional/channel comments (no user friction signal)
        lower = text.lower()
        if any(kw in lower for kw in ["subscribe", "check out my", "follow me", "visit my"]):
            continue

        video_id = item.get("video_id", "")
        record_id = "yt_" + str(item.get("id", _stable_id("yt", text[:30])))

        import datetime
        pub = item.get("published_at")
        try:
            created = datetime.datetime.fromisoformat(pub.replace("Z", "+00:00")) if pub else None
        except Exception:
            created = None

        review = ReviewMetadata(
            id=record_id,
            source="youtube",
            text=text,
            author=str(item.get("author", "Anonymous")),
            rating=None,
            created_at=created,
            url=f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
        )
        if _upsert(session, review):
            count += 1

    session.commit()
    logging.info("YouTube: inserted %d new records.", count)
    return count


# ---------------------------------------------------------------------------
# Source 3: Reddit
# ---------------------------------------------------------------------------

def clean_and_store_reddit(raw_data: list[dict], session) -> int:
    """
    Parse Arctic Shift / PRAW Reddit output and insert into SQLite.
    Fields: id, title, selftext, text, score, created_utc, url, subreddit, source
    """
    if not raw_data:
        logging.warning("Reddit: no raw data provided.")
        return 0

    count = 0
    for item in raw_data:
        text = (item.get("text") or "").strip()
        if len(text) < MIN_TEXT_LENGTH:
            continue

        # Skip purely meta posts (mod announcements, weekly threads, etc.)
        lower = text.lower()
        if any(kw in lower for kw in ["weekly thread", "mod post", "automoderator", "please read the rules"]):
            continue

        record_id = "reddit_" + str(item.get("id", _stable_id("r", text[:30])))

        import datetime
        created_utc = item.get("created_utc")
        try:
            created = datetime.datetime.utcfromtimestamp(float(created_utc)) if created_utc else None
        except Exception:
            created = None

        review = ReviewMetadata(
            id=record_id,
            source="reddit",
            text=text,
            author=None,
            rating=None,
            created_at=created,
            url=item.get("url"),
        )
        if _upsert(session, review):
            count += 1

    session.commit()
    logging.info("Reddit: inserted %d new records.", count)
    return count


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------

def run_cleaning_pipeline(
    raw_dir: str = "data/raw",
    db_path: str = "data/processed/reviews.db",
) -> None:
    """
    Run the full cleaning pipeline for all available raw sources.
    Each source is guarded by Path.exists() so missing files are skipped gracefully.
    """
    engine  = get_engine(db_path)
    session = get_session(engine)
    raw     = Path(raw_dir)
    totals  = {}

    # --- Play Store ---
    ps_path = raw / "play_store_reviews.json"
    if ps_path.exists():
        logging.info("Processing Play Store reviews ...")
        with open(ps_path, encoding="utf-8") as f:
            data = json.load(f)
        totals["play_store"] = clean_and_store_play_store(data, session)
    else:
        logging.warning("Play Store raw file not found, skipping.")

    # --- YouTube ---
    yt_path = raw / "youtube_comments.json"
    if yt_path.exists():
        logging.info("Processing YouTube comments ...")
        with open(yt_path, encoding="utf-8") as f:
            data = json.load(f)
        totals["youtube"] = clean_and_store_youtube(data, session)
    else:
        logging.warning("YouTube raw file not found, skipping.")

    # --- Reddit ---
    rd_path = raw / "reddit_posts.json"
    if rd_path.exists():
        logging.info("Processing Reddit posts ...")
        with open(rd_path, encoding="utf-8") as f:
            data = json.load(f)
        totals["reddit"] = clean_and_store_reddit(data, session)
    else:
        logging.warning("Reddit raw file not found, skipping.")

    # Summary
    total_inserted = sum(totals.values())
    logging.info("=" * 50)
    logging.info("Cleaning pipeline complete.")
    for source, count in totals.items():
        logging.info("  %-12s: %d records inserted", source, count)
    logging.info("  %-12s: %d total", "TOTAL", total_inserted)
    logging.info("=" * 50)


if __name__ == "__main__":
    run_cleaning_pipeline()
