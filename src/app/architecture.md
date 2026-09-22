# Dashboard and API architecture

`api.py` serves the static dashboard and reads the existing SQLite database. `/api/data` combines active source-scoped review counts, versioned AI analysis status, and a separate `csv_import` reconciliation from `csv_import_ledger`. Manual CSV labels do not contribute to AI retrieval findings.

The frontend renders aggregate counts, supported failure-mechanism cards, and run status. The browser-side Retrieval Evidence Review section and its script include are commented out while classification quality is reviewed. The saved assessments and `/api/research/evidence` endpoint are retained for later use.

The mechanism chart includes only records with a source-supported mechanism. Reported failures with unclear causes, successful retrieval, and retrieval needs without an outcome have separate counts. Failed classifications show provider-limit, source-evidence, batch-output, and other error groups, without leaking record text or credentials.

## Mobile layout contract

Overview and Chat share a 768px breakpoint in `static/style.css`:

- Overview: `.insights-dashboard` collapses to one column and all `.col-span-*` / `.insight-card.wide` / `.insight-row` spans reset to `grid-column: 1 / -1` so cards stack instead of inventing extra grid tracks. `.insight-row-3` also collapses to one column. `.verbatims-grid` uses `minmax(0, 1fr)` on narrow viewports (multi-column `auto-fit` from 640px up). Chart wrappers use `.overview-chart` with taller mobile height; Chart.js moves doughnut legends to the bottom and truncates long bar labels under 768px.
- Chat: both `.chat-sidebar` (Suggestion chips) and `.chat-context-panel` (Active Context) are hidden. `#tab-chat .ai-discovery-engine` fills the remaining viewport height. Legacy FAB popup rules at 1024px stay disabled so they do not fight the tab layout.
- Desktop Chat: `#tab-chat` is sized under the header and tabs with tight padding. `body.chat-tab-active` locks page scroll so only the message list (and side panels if content overflows) scrolls. Overview keeps normal document scrolling.

## Discovery Insights tiles

Overview Discovery Insights includes: Top Discovery Signals, Search Methods, Frustration Severity, Top Failing Entities, Remembered Clues (what users still recall), and Journey Breakdown (which search step failed). Aggregates come from `catalog_snapshot` in `catalog_dashboard.py` using assessment tags already stored in SQLite.

The second insight row (Failing Entities, Remembered Clues, Journey Breakdown) uses a full-width `.insight-row-3` wrapper so the three cards share equal width and do not leave an empty fourth column in the 4-column grid.

Dataset Overview labels use plain product language (Catalog Rows, AI Assessed Rows, Possible Issue Patterns, Possible User Reports). Each stat card and the section title have an info tooltip explaining the metric in plain English.

## Chat Suggestion chips and guardrails

The Chat tab Suggestion sidebar lists the four incomplete-memory research questions first (kinds of old photos, what people remember, what they forgot, how they search with incomplete memory), then two general retrieval chips. `/api/chat` routes to `catalog_chat.py`, which enforces Google Photos-only scope and prompt-injection resistance in the system prompt.
