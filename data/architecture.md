# Discovery engine runtime data

`processed/reviews.db` is the SQLite source of truth for collected feedback, exclusions, the combined CSV import ledger, and versioned research results. `processed/reviews-before-combined-import-20260919.db` is a local pre-import backup. Chroma search data and dashboard insight artifacts also live under `processed/`.

`research/` contains resumable run reports and prior API pause history. The September 19 user authorization resumed paid mini-model classification. A first-pass-only run currently processes unseen records and leaves failures for a later AI pipeline. Runtime database and credential files must not be published as examples without a separate data and secrets review.

The September 20 Phase 1 rebuild replaced the active `processed/reviews.db` with a fresh catalog import. It currently contains 692 source-scoped candidate records and a ledger for all 3,000 CSV rows. The old database is temporarily held as `processed/reviews-old-awaiting-verification.db` until new issue processing and API checks pass. Historical raw, vector, and research artifacts are not part of the active Phase 1 findings and are scheduled for removal after verification.

After the full-scope correction, `processed/reviews.db` also contains 3,000 active `phase1_catalog_rows`. These include direct source records, web summaries, and generated scenarios. The `phase1_catalog_assessments` table is reserved for versioned AI decisions over this full catalog. The older 692-row review table is no longer the intended Phase 1 denominator.
