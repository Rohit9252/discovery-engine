"""
Apple App Store review collector for the Google Photos Discovery Engine.

Uses the app-store-scraper library with retry logic and proper session handling.
Falls back to direct iTunes RSS API if the library is blocked.

Usage:
    uv run python src/collect/app_store.py

Output:
    data/raw/app_store_reviews.json
"""

import json
import logging
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

APP_ID   = 962194608
APP_NAME = "google-photos"
COUNTRY  = "us"
TARGET   = 200


# ---------------------------------------------------------------------------
# Primary: app-store-scraper with retry
# ---------------------------------------------------------------------------

def scrape_via_library(count: int = TARGET) -> list[dict]:
    """Try app-store-scraper library with up to 3 retries."""
    try:
        from app_store_scraper import AppStore
    except ImportError:
        logging.error("app-store-scraper not installed. Run: uv add app-store-scraper")
        return []

    for attempt in range(1, 4):
        try:
            logging.info("Library attempt %d/3 ...", attempt)
            app = AppStore(country=COUNTRY, app_name=APP_NAME, app_id=APP_ID)
            app.review(how_many=count)
            reviews = app.reviews or []
            logging.info("Library returned %d reviews.", len(reviews))
            if reviews:
                return reviews
        except Exception as exc:
            logging.warning("Library attempt %d failed: %s", attempt, exc)
        time.sleep(3)

    return []


# ---------------------------------------------------------------------------
# Fallback: iTunes RSS feed (no scraping, Apple's own public feed)
# ---------------------------------------------------------------------------

def scrape_via_rss(pages: int = 10) -> list[dict]:
    """
    Fetch reviews via Apple's public iTunes RSS feed.
    Returns up to pages*50 reviews (50 per page, max 10 pages = 500 reviews).
    No library needed - pure HTTP + JSON parsing.
    """
    import requests

    reviews = []
    logging.info("Falling back to iTunes RSS API ...")

    for page in range(1, pages + 1):
        url = (
            f"https://itunes.apple.com/{COUNTRY}/rss/customerreviews/"
            f"page={page}/id={APP_ID}/sortby=mostrecent/json"
        )
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            entries = data.get("feed", {}).get("entry", [])
            if not entries:
                logging.info("No more entries at page %d, stopping.", page)
                break

            for entry in entries:
                # Skip the first entry on page 1 which is app metadata, not a review
                if "im:rating" not in entry:
                    continue

                review_id = entry.get("id", {}).get("label", f"rss_{page}_{len(reviews)}")
                reviews.append({
                    "id":      review_id,
                    "title":   entry.get("title", {}).get("label", ""),
                    "review":  entry.get("content", {}).get("label", ""),
                    "rating":  int(entry.get("im:rating", {}).get("label", 0)),
                    "author":  entry.get("author", {}).get("name", {}).get("label", "Anonymous"),
                    "date":    entry.get("updated", {}).get("label", ""),
                    "version": entry.get("im:version", {}).get("label", ""),
                })

            logging.info("Page %d: %d total reviews so far.", page, len(reviews))
            time.sleep(0.5)

        except Exception as exc:
            logging.error("RSS page %d failed: %s", page, exc)
            break

    return reviews


# ---------------------------------------------------------------------------
# Normalize to common schema
# ---------------------------------------------------------------------------

def normalize(reviews: list[dict], source: str) -> list[dict]:
    """Normalize library OR rss output to a consistent schema."""
    normalized = []
    for r in reviews:
        if source == "library":
            text = str(r.get("review", "") or r.get("content", "") or "")
            title = str(r.get("title", "") or "")
            rating = r.get("rating")
            author = str(r.get("userName", "") or r.get("author", "") or "Anonymous")
            date   = str(r.get("date", "") or "")
        else:  # rss
            text   = str(r.get("review", ""))
            title  = str(r.get("title", ""))
            rating = r.get("rating")
            author = str(r.get("author", "Anonymous"))
            date   = str(r.get("date", ""))

        if not text.strip() or len(text) < 10:
            continue

        normalized.append({
            "id":     str(r.get("id", f"ios_{len(normalized)}")),
            "title":  title,
            "review": text,
            "rating": rating,
            "author": author,
            "date":   date,
        })
    return normalized


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_reviews(reviews: list[dict], output_file: str = "data/raw/app_store_reviews.json") -> None:
    if not reviews:
        logging.warning("No App Store data to save.")
        return
    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    logging.info("Saved %d App Store reviews to %s", len(reviews), output_file)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.info("=== App Store Collector Start ===")

    # Try library first
    raw = scrape_via_library(count=TARGET)
    if raw:
        reviews = normalize(raw, "library")
        logging.info("Library path: %d reviews normalized.", len(reviews))
    else:
        # Fallback to iTunes RSS
        raw = scrape_via_rss(pages=6)
        reviews = normalize(raw, "rss")
        logging.info("RSS path: %d reviews normalized.", len(reviews))

    save_reviews(reviews)
    logging.info("=== App Store Collector Done ===")
