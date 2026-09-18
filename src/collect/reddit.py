"""
Reddit data collector for the Google Photos Discovery Engine.

Uses the Arctic Shift API (https://arctic-shift.photon-reddit.com) - a free,
unauthenticated Reddit archive. No API keys or credentials required.

Strategy:
  - Search r/googlephotos, r/GooglePixel, r/Android, r/photography using
    targeted title keywords that match discovery failure patterns
  - Also fetch top comments from high-signal post IDs via the comments/search endpoint
  - Deduplicate everything by post/comment ID before saving

Usage:
    uv run python src/collect/reddit.py

Output:
    data/raw/reddit_posts.json
"""

import json
import logging
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://arctic-shift.photon-reddit.com/api"

# 4 subreddits as specified in [REF-1] Stage 1 - Collect
TARGET_SUBREDDITS = [
    "googlephotos",
    "GooglePixel",
    "Android",
    "photography",
]

# Title keywords targeting discovery failure patterns
# Arctic Shift supports `title` parameter for keyword filtering within subreddit
TITLE_KEYWORDS = [
    "ask photos",
    "gemini search",
    "can't find",
    "search",
    "find photo",
    "old photos",
    "photo retrieval",
    "missing",
    "retrieve",
]

# Known high-signal post IDs (Ask Photos complaint threads from [REF-1] Section 1)
# We fetch top comments from these directly via the comments/search endpoint
HIGH_SIGNAL_POST_IDS = [
    "1dqw3p4",  # "Ask Photos is a huge downgrade"
    "1cxkqzm",  # "Google Photos search has gotten worse"
    "1dyq9k2",  # "Ask Photos is terrible" (r/Android)
    "1ezm4tp",  # "Classic search vs Ask Photos"
    "1b8k3mn",  # Google Photos discovery failure thread
]

POSTS_PER_QUERY   = 100   # limit per subreddit+keyword request (Arctic Shift max = 100)
COMMENTS_PER_POST = 30    # top comments per high-signal thread
RATE_LIMIT_SLEEP  = 0.8   # seconds between requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(endpoint: str, params: dict, timeout: int = 20) -> list[dict]:
    """Make a GET request to Arctic Shift and return the data list."""
    url = f"{BASE_URL}/{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data") or []
    except Exception as exc:
        logging.error("Arctic Shift request failed [%s params=%s]: %s", endpoint, params, exc)
        return []


# ---------------------------------------------------------------------------
# Collector: Posts by subreddit + title keyword
# ---------------------------------------------------------------------------

def scrape_posts_by_keyword(
    subreddits: list[str] = TARGET_SUBREDDITS,
    keywords: list[str]   = TITLE_KEYWORDS,
    limit: int            = POSTS_PER_QUERY,
) -> dict[str, dict]:
    """
    For each subreddit + keyword, fetch posts whose titles match.
    Returns deduplicated dict keyed by post ID.
    """
    all_posts: dict[str, dict] = {}

    for subreddit in subreddits:
        for keyword in keywords:
            logging.info("Fetching r/%s | title keyword: '%s'", subreddit, keyword)
            items = _get(
                "posts/search",
                {
                    "subreddit": subreddit,
                    "title":     keyword,
                    "limit":     limit,
                    "sort":      "desc",
                },
            )

            new = 0
            for item in items:
                post_id = item.get("id")
                if not post_id or post_id in all_posts:
                    continue

                selftext = item.get("selftext", "") or ""
                if selftext in ("[removed]", "[deleted]"):
                    selftext = ""

                combined = (item.get("title", "") + " " + selftext).strip()
                if len(combined) < 20:
                    continue

                all_posts[post_id] = {
                    "id":          post_id,
                    "title":       item.get("title", ""),
                    "selftext":    selftext,
                    "text":        combined,
                    "score":       item.get("score", 0),
                    "created_utc": item.get("created_utc"),
                    "url":         "https://www.reddit.com" + (item.get("permalink") or ""),
                    "subreddit":   subreddit,
                    "source":      "reddit",
                }
                new += 1

            logging.info("  -> %d new posts", new)
            time.sleep(RATE_LIMIT_SLEEP)

    logging.info(
        "Post search phase complete: %d unique posts.", len(all_posts)
    )
    return all_posts


# ---------------------------------------------------------------------------
# Collector: Top comments from high-signal threads
# ---------------------------------------------------------------------------

def scrape_comments_from_threads(
    post_ids:    list[str] = HIGH_SIGNAL_POST_IDS,
    max_results: int       = COMMENTS_PER_POST,
) -> dict[str, dict]:
    """
    Fetch top comments from known high-signal Ask Photos complaint threads.
    Uses Arctic Shift's comments/search endpoint filtered by link_id.
    """
    all_comments: dict[str, dict] = {}

    for post_id in post_ids:
        logging.info("Fetching comments for post ID: %s", post_id)
        items = _get(
            "comments/search",
            {
                "link_id": f"t3_{post_id}",
                "limit":   max_results,
                "sort":    "desc",
            },
        )

        new = 0
        for item in items:
            comment_id = item.get("id")
            body = item.get("body", "") or ""

            if not comment_id or body in ("[removed]", "[deleted]") or len(body) < 30:
                continue

            key = f"comment_{comment_id}"
            if key in all_comments:
                continue

            # Prefix with link_id so we can find it back; body is the content
            all_comments[key] = {
                "id":          key,
                "title":       f"Comment on post {post_id}",
                "selftext":    body,
                "text":        body,
                "score":       item.get("score", 0),
                "created_utc": item.get("created_utc"),
                "url":         f"https://www.reddit.com/comments/{post_id}",
                "subreddit":   item.get("subreddit", "googlephotos"),
                "source":      "reddit",
            }
            new += 1

        logging.info("  -> %d new comments", new)
        time.sleep(RATE_LIMIT_SLEEP)

    logging.info(
        "Comment fetch phase complete: %d unique comments.", len(all_comments)
    )
    return all_comments


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_reddit_data(
    records:     list[dict],
    output_file: str = "data/raw/reddit_posts.json",
) -> None:
    """Save all records to a single JSON file."""
    if not records:
        logging.warning("No Reddit data to save.")
        return

    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    logging.info("Saved %d Reddit records to %s", len(records), output_file)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.info("=== Reddit Collector Start (Arctic Shift API) ===")
    logging.info(
        "Targeting %d subreddits x %d keywords + %d direct threads",
        len(TARGET_SUBREDDITS), len(TITLE_KEYWORDS), len(HIGH_SIGNAL_POST_IDS),
    )

    posts    = scrape_posts_by_keyword()
    comments = scrape_comments_from_threads()

    merged = {**posts, **comments}
    final  = list(merged.values())
    logging.info("Total unique Reddit records: %d", len(final))

    save_reddit_data(final)
    logging.info("=== Reddit Collector Done ===")
