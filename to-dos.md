# Discovery Engine - To-Dos

## Done
- Seed data + UI pushed; PR merged into `main`
- Render config targets **`main` only** (`render.yaml` + README)
- Build uses `uv` + `requests` override to fix Render pip conflict

## Your Render settings (main only)

1. Branch: **`main`** (not the feature branch)
2. Build: `pip install uv && uv pip install --system -r requirements.txt --override requests>=2.31.0`
3. Start: `uvicorn src.app.api:app --host 0.0.0.0 --port $PORT`
4. Env: `OPENAI_API_KEY`
5. Auto-deploy on

## Standing rule
Compute locally → push to `main` → Render serves `reviews.db` + `chroma_db` as-is. No recompute on Render.
