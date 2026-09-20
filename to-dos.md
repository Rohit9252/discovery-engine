# Discovery Engine - To-Dos

## Agent work (done)

- Un-ignored and committed `data/processed/chroma_db/` (~19 MB)
- Kept `data/processed/reviews.db` as seed SQLite
- Added `Procfile` + `render.yaml` (uvicorn only, no pipeline)
- Documented standing rule + Render steps in README / architecture
- Pushed commit `3ccfa70` to `feature/discovery-engine-overhaul`

## Your next steps (only you can do these)

1. Have ready: GitHub access, Render account, `OPENAI_API_KEY`
2. Render → New Web Service → repo `Rohit9252/discovery-engine` → branch `feature/discovery-engine-overhaul`
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn src.app.api:app --host 0.0.0.0 --port $PORT`
5. Env: `OPENAI_API_KEY` = your key; enable auto-deploy
6. Verify Overview + Chat on the live URL, then send that URL back

## Standing rule

Compute locally → push `reviews.db` + `chroma_db` → Render serves as-is. Never recompute on the platform.
