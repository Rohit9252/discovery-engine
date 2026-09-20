# Combined CSV import architecture

`combined_csv.py` reads only positive-label rows from the root combined CSV. The source file stays read only. Every one of those rows receives a stable content-derived ID and a decision in `csv_import_ledger` inside the existing SQLite database.

The ledger separates imported source-scoped records, records already present in `reviews_metadata`, and held records. Held reasons include derived or secondary content, missing links, and unconfirmed Google Photos context. The importer places only source-scoped candidates into `reviews_metadata`. CSV category and relevance remain manual metadata in the ledger; they never become AI research labels.

The import runs in one SQLite transaction and skips previously staged IDs on repeat execution. Existing feedback is not edited. The research pipeline can assess new `reviews_metadata` rows separately and persists its own versioned assessments.

`phase1_catalog.py` is the approved September 20 replacement import. It reads the 3,000-row preprocessing CSV with Pandas, stages each row in a fresh database ledger, and imports only source-scoped candidate feedback. Synthetic scenarios, paraphrased web summaries, secondary/derived rows, missing links, and unconfirmed product context remain held with explicit reasons. The catalog stays unchanged. A dedicated test covers source separation, duplicate source text, row reconciliation, and idempotent reruns. The initial import reconciled 692 active source candidates and 2,308 held rows.

The corrected full-scope import also writes every CSV row to `phase1_catalog_rows`, using a row-position ID and a hash of the complete row. Reimport updates changed rows and marks current rows active. The root Phase 1 classifier and application must use this table as their complete 3,000-row source. The older ledger and 692-row review table remain only for transition and audit, and their held status does not exclude catalog rows from AI assessment.
