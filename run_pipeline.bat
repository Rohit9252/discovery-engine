@echo off
echo Running full Discovery Engine data pipeline...
echo.

echo [1/6] Scraping Play Store...
uv run python src\collect\play_store.py

echo [2/6] Scraping App Store...
uv run python src\collect\app_store.py

echo [3/6] Scraping Reddit...
uv run python src\collect\reddit.py

echo [4/6] Cleaning Data into SQLite...
uv run python src\process\clean.py

echo [5/6] Extracting Insights and Indexing into ChromaDB...
uv run python src\process\run_extraction.py

echo [6/6] Pipeline Complete! You can now use the Streamlit app.
