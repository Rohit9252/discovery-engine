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


## September 18 baseline correction (authoritative current behavior)

The user approved retaining FastAPI/static HTML and OpenAI while fixing the application. Earlier Gemini/Streamlit descriptions above are historical and do not describe the active dashboard.

- `src/process/paths.py` owns absolute project-relative SQLite and Chroma locations. Default storage no longer depends on launch working directory. Explicit test database paths remain supported.
- `src/process/dashboard.py` is the shared provisional aggregation component. Whole-word topic patterns produce both chart counts and evidence cards from the same stored population. Topic membership overlaps and includes positive feedback. No validated retrieval failure-stage counts are currently available.
- `src/app/api.py` serves static assets, health identity, provisional counts, source-linked examples, and the existing research chat. Database sessions close and engines dispose after dashboard requests. Blocking work runs in FastAPI sync route workers. Errors return actionable 503 responses without exposing exception details.
- `src/app/static/` retains the Material-inspired layout. It labels provisional evidence, shows API failures instead of zeros, escapes dashboard quote text, validates source URL schemes, and uses versioned CSS/JS URLs. Topic counts can render as text if Chart.js is unavailable. The active UI uses Overview Stats and Chat tabs. Under 768px, `.insights-dashboard` is a single column with `.col-span-*` reset to full width, `.verbatims-grid` uses `minmax(0, 1fr)`, and Chat hides both `.chat-sidebar` and `.chat-context-panel` so only the conversation surface remains. On desktop, Chat fills `calc(100dvh - 116px)` under the chrome with `body.chat-tab-active` locking page scroll so only the message list scrolls.

## Render deploy and seed data

Standing rule: compute scrape/extract/index **locally**, commit `data/processed/reviews.db` and `data/processed/chroma_db/`, push, and let Render serve those files. Render start is uvicorn only (`Procfile` / `render.yaml`). No collectors, extraction runners, or Chroma rebuild on the platform. Live Chat still needs `OPENAI_API_KEY` in Render Environment for answering questions; that is not corpus reprocessing. Paths come from `src/process/paths.py` (`REVIEW_DATABASE`, `VECTOR_DATABASE`).
- `start.ps1` selects the project directory and invokes `uv run uvicorn src.app.api:app --host 127.0.0.1 --port 8000`. Reload is optional. The script does not terminate arbitrary future port occupants. The confirmed orphaned old server was stopped during this approved repair.
- `/api/health` reports version `baseline-1` and the expected SQLite location. Server logs from this session live under ignored `data/logs/`.

Verification: six API/storage regressions passed. SQLite and Chroma ID sets matched exactly at 558 records. Desktop/mobile document overflow checks and the mobile chat toggle passed. The active app is on port 8000; the older port 8001 and Streamlit processes were not changed. Chat relevance/grounding repair and validated retrieval extraction are still pending later steps.


## Research-status UI correction

`dashboard.py` now emits a structured `research_status`: pending_review when records exist, no_data when empty, and null for the unknown validated retrieval count. The current provisional engine has no persisted reviewed retrieval analysis, so the UI does not claim that previous extraction failed or that there are zero retrieval stories.

`static/research-status.js` renders lists using textContent and replaceChildren, handles missing status explicitly, and distinguishes Not assessed from unavailable requests. The dashboard now contains four readiness details, four actionable research steps, and a retrieval analysis checklist. Calm blue styling replaces the failure-like alarm icon/red badge. The current FastAPI and OpenAI stack is retained.

Verification: six API/storage tests and a standalone Node research-status rendering test pass. Desktop/mobile screenshots and the next E1-E7 plan are linked from `Docs/discovery-engine-evidence-phase-plan.md`. No new extraction, scraping, or manually verified research evidence is implied by these UI status changes.


## Approved same-day collector audit and refresh

The current collector package separates source configuration (`config.py`), sanitized bounded HTTP retries (`http_client.py`), atomic raw merges/snapshots/receipts (`storage.py`), source modules, and parallel orchestration (`refresh.py`). Reddit scans recent subreddit pages and locally matches title/body terms because remote keyword searches timed out. Comment parents are retrieved product-scoped posts, not the five incorrect historical IDs. Play Store consumes continuation tokens. Apple RSS ingestion works through stable normalized IDs and a dedicated cleaner. YouTube targets are verified using video metadata and comments are paginated with exact comment links. Receipts disclose page caps and source limitations.

`ReviewExclusion` preserves historical source-context gaps without deleting `ReviewMetadata`. `source_audit.py` provides the shared active_reviews query and a source-context exclusion report. API totals distinguish 1,869 stored from 1,731 available and 138 excluded. Source-scoped records remain candidate feedback, not confirmed retrieval stories.

`index_feedback.py` refreshes raw-feedback embeddings in batches with stable-ID upserts and removes reversible exclusions from search. It does not call the paid OpenAI extraction pipeline or assign research failure labels. Existing paid chat synthesis still needs the relevance/grounding repair described in the evidence-phase plan.

30 targeted tests passed, including continuation tokens, title/body product gates, incorrect videos, retry hygiene, durable saves, iOS normalization/ingestion, short contextual complaints, reversible exclusions, and stable-ID index updates. Detailed counts, limitations, screenshots, and repeat commands are in `Docs/discovery-engine-collection-audit.md`. No public deployment occurred.

## Approved retrieval analysis implementation

The September 18 user request explicitly authorizes analysis of the collected records. The existing FastAPI and OpenAI stack exceptions remain in effect. `research_schema.py` defines strict retrieval relevance, explicit incomplete-memory evidence, outcomes and failure mechanisms. `research_extract.py` uses bounded structured batches and rejects fabricated spans or mismatched IDs. `research_store.py` persists source-hashed, versioned results in separate SQL tables. `research_runner.py` checkpoints each completed batch, excludes quarantined feedback, prevents concurrent runs, and resumes failed or unfinished records. Nine targeted tests pass, including provider failure states, duplicate IDs, source changes and successful resume. The original reviews remain untouched. AI assessment is distinct from human review.

### Saved research dashboard integration

`research_dashboard.py` calculates successful, unrelated, relevant, explicit-memory, pending and failed counts from current-version assessments whose source hashes match active reviews. A run heartbeat distinguishes processing from an interrupted run. `/api/research/evidence` supports bounded pagination and explicit-memory filtering. The existing Material-inspired dashboard now displays AI finding groups and inspectable verbatim clues, missing details, attempted searches, workarounds, outcomes and original feedback. Unknown fields are shown as not reported. Human-reviewed counts remain zero; source-span validation alone is not semantic validation. Seventeen targeted Python checks and frontend status/syntax checks pass. The full corpus processing run is active and durable checkpoints are being saved.

### Interpretation quality and export

The first live batch exposed an editing false positive and inferred memory details. `retrieval-v2` supersedes the initial version without altering source feedback. The full-corpus first pass is followed by `--review-candidates`, which uses GPT-4.1 to re-assess every positive, retrieval-language negative and failed record, with the same identity and literal-span safeguards. Saved model provenance distinguishes both passes. A stated bare year cannot qualify as forgotten information. This is a second AI check, not human validation. `research_report.py` exports all relevant source-linked labels, reconciled counts, missing-field coverage and sampling limitations. Nineteen targeted Python tests pass; previous frontend status and syntax checks also pass.

### Provider limit correction

The initial GPT-4.1 verification run hit token rate limits. Its successful saved results are retained. GPT-4.1-mini passed all six live labeling boundary fixtures and resumes failed candidates with shared token-based pacing in `research_rate_limit.py`. The observed GPT-4.1-mini response limit was 200,000 tokens/minute; the configured pacing budget is a conservative 120,000, including output allowance. Explicit cooldown applies across workers after a provider 429. Exhausted account quota is terminal rather than retried as ordinary rate limiting. New phase progress is persisted separately in `research_run_progress`, avoiding destructive schema changes. Twenty-five targeted tests pass, including rate pacing, cooldown, account quota handling and complete workflow orchestration. These remain AI assessments, not human validation.

### User-requested API pause

Paid processing was stopped at the user's explicit request due to charges. The worker and uv parent were terminated; research run status is paused. `API_PAUSE_FILE` in `paths.py` records a durable user pause. Research client initialization and `/api/chat` reject calls while that flag exists. Dashboard and evidence endpoints remain read-only and display paused status. Existing successful results are preserved; analysis is incomplete. One local pause test and frontend status rendering checks pass without external calls. Further paid work requires explicit approval, and no automatic restart has been scheduled.

## September 19 combined CSV import and classifier operation

The user approved importing only the 1,813 positive-label rows from the 2,979-row root combined CSV. `src/ingest/combined_csv.py` writes one provenance decision per positive-label row to `csv_import_ledger` in the existing SQLite database. It inserted 1,198 new `reviews_metadata` rows, linked 32 existing records, and held 583 derived, unlinked, or product-scope-unconfirmed rows. The total database count is 3,067, including 138 earlier reversible exclusions. A pre-import database copy is retained locally. The source CSV and pivot files remain read only.

The dashboard API reports the import reconciliation separately from AI retrieval findings. `research_dashboard.py` counts supported failure mechanisms separately from failures with unclear causes and retrieval needs or successes without a reported failure. The Retrieval Evidence Review browser section is temporarily commented out at the user's request. Saved assessments and its read-only API remain for later consideration.

The user explicitly reauthorized paid calls after the earlier pause. The active first-pass run uses only `gpt-4o-mini`, four workers, four-record batches, and `--skip-failed`. Existing failed records stay saved for the later AI pipeline requested by the user. New errors receive safe per-record reason codes rather than source text. Legacy errors retain their broad saved codes. No full-size OpenAI model is scheduled by this command.

The approved September 20 Phase 1 rebuild uses the preprocessing 3,000-row catalog as its only input. `src/ingest/phase1_catalog.py` separates 692 source-scoped candidate records from 2,308 held synthetic, paraphrased, secondary, or unconfirmed rows in a fresh SQLite database. The root issue classifier will assess the candidates; held rows cannot enter dashboard issue counts or chatbot evidence. The prior active database remains temporarily available only for rollback until the replacement passes end-to-end checks.

The user then clarified that all 3,000 rows are in scope for AI assessment and retrieval-pattern exploration. `phase1_catalog_rows` now holds every row as an active catalog item, with source type and a full-row hash. The older 692-row review table and issue classifier are transitional; the new catalog runner, dashboard, and chat must read all 3,000 rows. Source reports and generated scenarios remain separate evidence classes in displayed findings.

Cloudflare Workers AI credentials live only in the ignored `.env`. `src/process/cloudflare_screen.py` is an isolated GLM 4.7 Flash pilot with strict source-quote validation, usage metering, and durable independent results. A live JSON-schema request succeeded, but the full screening pilot has not passed the quality gate and is not processing the corpus. Cloudflare's allowance is 10,000 neurons per day, not requests. Provider coordination and supervisor decisions are future work after validation; simultaneous duplicate calls against the same record are avoided.

The GLM 4.7 pilot was subsequently removed at the user's request because it was not working. Its module, tests, and example credentials are no longer part of the active project. The full Phase 1 assessment uses OpenAI.

The new `src/process/catalog_schema.py`, `catalog_extract.py`, `catalog_store.py`, and `catalog_runner.py` provide assignment-focused multi-tag assessment over all 3,000 catalog rows. A mixed pilot showed distinct decisions for source issues, related advice, a search feature request, a paraphrased face-grouping issue, and a generated scenario. The current assessment version is stored separately from the older issue classifier so its results can be audited and refreshed without altering the CSV.
