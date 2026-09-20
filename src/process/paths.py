"""Project-relative storage and configuration locations."""
from pathlib import Path

import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DATABASE = PROJECT_ROOT / 'data' / 'processed' / 'reviews.db'
VECTOR_DATABASE = PROJECT_ROOT / 'data' / 'processed' / 'chroma_db'
API_PAUSE_FILE = PROJECT_ROOT / 'data' / 'research' / 'api-paused.json'
