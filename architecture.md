# Discovery Engine Architecture

## Component Overview
The Discovery Engine is a decoupled pipeline designed to proactively scrape, clean, and extract product insights from public Google Photos reviews across multiple platforms.

## Current State & Modules

### 1. Collection Layer (`src/collect/`)
Responsible for fetching raw data from external sources and saving it to `data/raw/` as JSON.
*   **Play Store (`play_store.py`)**: Uses the unofficial `google-play-scraper` to pull the latest reviews for `com.google.android.apps.photos`. It bypasses pagination limits and grabs recent reviews (regardless of star rating) to maximize our chance of finding UX pain points.
*   **App Store (`app_store.py`)**: Uses `app-store-scraper` to pull iOS user reviews for Apple App ID `962194608`, ensuring we don't have Android platform bias in our dataset.
*   **Reddit (`reddit.py`)**: Uses the unauthenticated `requests` library to scrape `r/googlephotos/search.json`. Features a custom User-Agent and timed delays to safely bypass Reddit's bot-blocks.
*   **YouTube (`youtube.py`)**: Uses the official `youtube/v3/commentThreads` REST API endpoint to pull top-level comments from popular Google Photos tutorial videos, identifying learning-curve pain points.
*   **Google Forums (`forums.py`)**: Uses `requests` and `BeautifulSoup` to scrape recent bug reports directly from the Google Photos Support Community (`support.google.com`).

### 2. Processing Layer (`src/process/`)
Responsible for data cleaning and metadata storage.
*   **Database (`db.py`)**: Uses SQLAlchemy to define a unified `ReviewMetadata` schema and initialize a local SQLite database (`data/processed/reviews.db`) for robust querying.
*   **Data Cleaning (`clean.py`)**: Uses `pandas` to load raw JSON data, deduplicate, drop null entries, standardize column schemas across platforms, and push cleaned metadata to SQLite.

### 3. Extraction & Vector Store (`src/process/`)
Responsible for converting unstructured text into structured insights and vector embeddings.
*   **Pydantic Schema (`schema.py`)**: Defines `ReviewExtraction`, `InsightClue`, and `Workaround` models to force the LLM into returning predictable, typed JSON.
*   **Vector Database (`vector_db.py`)**: Initializes ChromaDB to store text embeddings, powering semantic search for the final RAG pipeline.
*   **LLM Extraction (`extract.py`)**: Uses LangChain and Google's `gemini-1.5-flash` model to analyze review text and extract structured insights based on the Pydantic schema.

### 4. Application Layer (`src/app/`)
Responsible for rendering the final Discovery Engine PM dashboard as a high-fidelity web application.
*   **FastAPI Backend (`api.py`)**: A decoupled REST API server that routes HTTP endpoints. It serves the static HTML/CSS/JS files and exposes `/api/data` for chart hydration and `/api/chat` to interface with the LangGraph backend.
*   **Frontend Presentation (`static/`)**: A pure HTML/CSS/JS web application utilizing a premium, light-themed Material 3 design system.
    *   **Split-Pane Layout**: The UI is divided into two distinct sections:
        *   **Scrollable Left Pane (Data Showcase)**: Presents the empirical evidence in a dense, scannable format, featuring:
            *   *Dataset Overview:* KPI metrics for ingestion.
            *   *Top Discovery Insights:* Thematically clustered user quotes and PM takeaways.
            *   *Strongest Signal:* A hero card highlighting the most critical pain point (e.g., Contextual & Temporal Search Failures).
            *   *Analytics Charts:* Chart.js visualisations for Failure Stages and Pain Point Themes.
            *   *Pipeline Architecture:* A visual diagram of the backend processing flow.
        *   **Sticky Right Pane (AI Assistant)**: A persistent chat interface that queries the LangGraph RAG pipeline, providing conversational access to the dataset without losing context of the dashboard metrics.

## Data Storage
*   `data/raw/play_store_reviews.json`: Raw JSON dump of Play Store reviews.
