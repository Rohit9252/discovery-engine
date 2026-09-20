# Discovery Engine - To-Dos

## Render deploy (seed data, no platform recompute)

### Agent: wiring and push
- **Why**: Ship UI fixes plus `reviews.db` + `chroma_db` so Render serves Overview/Chat without re-scrape/extract/index.
- **Impact**: Live demo uses the same processed artifacts; future pushes of updated seed files redeploy without recomputation.
- **Status**: In progress

### You: Render account prerequisites
- **Why**: Only you can authorize GitHub + Render and hold `OPENAI_API_KEY`.
- **Impact**: Unlocks creating the Web Service.
- **Status**: Ready for you (see README Deploy to Render)

### You: create Web Service + env + verify
- **Why**: Dashboard settings and secrets cannot be set by the agent.
- **Impact**: Public URL for Overview + Chat.
- **Status**: Ready for you after push (exact table in README)

## Standing rule
Compute locally → commit `reviews.db` + `chroma_db` → push → Render serves as-is. Never put pipeline scripts in Render start/build.
