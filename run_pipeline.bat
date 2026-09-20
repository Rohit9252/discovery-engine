@echo off
setlocal
pushd "%~dp0"
echo [1/4] Refreshing public feedback with source verification and snapshots...
uv run python -m src.collect.refresh
if errorlevel 1 goto failed
echo [2/4] Cleaning and ingesting all available sources...
uv run python -m src.process.clean
if errorlevel 1 goto failed
echo [3/4] Auditing source context and refreshing semantic feedback search...
uv run python -m src.process.source_audit
if errorlevel 1 goto failed
uv run python -m src.process.index_feedback
if errorlevel 1 goto failed
echo [4/4] Collection and ingestion complete. Inspect data\collection-runs\latest-summary.json for partial source failures.
echo Start the dashboard with: uv run uvicorn src.app.api:app --host 127.0.0.1 --port 8000
echo Optional existing AI extraction/indexing: uv run python -m src.process.run_extraction
echo The existing extractor is not yet a validated memory-specific research pipeline.
popd
exit /b 0
:failed
echo Pipeline failed. See the source errors above; existing evidence has been preserved.
popd
exit /b 1
