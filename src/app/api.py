"""
FastAPI backend for the Google Photos Discovery Engine.
Serves the static frontend and provides REST endpoints for the LangGraph
Corrective-RAG agent and analytics chart data.
"""
import os
import sys
from pathlib import Path

# Ensure project root is on the path so src.process modules resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Google Photos Discovery Engine API")

# Mount the static folder so CSS/JS/images are served automatically
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the main HTML application."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/data")
async def get_chart_data():
    """
    Returns aggregated chart data from the SQLite database for the analytics
    section: Failure Stage counts and Pain Point Theme counts.
    Uses keyword heuristics over the review text since full LLM extraction
    may not have run yet (resource-intensive for large datasets).
    """
    try:
        from src.process.db import get_engine, get_session, ReviewMetadata

        engine = get_engine()
        session = get_session(engine)
        reviews = session.query(ReviewMetadata).all()

        stage_counts: dict[str, int] = {}
        theme_counts: dict[str, int] = {}

        stage_keywords = {
            "Discovery":      ["find", "discover", "notice", "aware", "locked folder", "where is", "missing"],
            "Execution":      ["crash", "bug", "broken", "fail", "error", "does not work", "stuck",
                               "freeze", "backup", "face tag", "edit", "search", "tagging", "receipt",
                               "scrolling", "workaround"],
            "Post-Execution": ["missing", "gone", "deleted", "transfer", "album", "lost", "after"],
        }
        theme_keywords = {
            "Search":       ["search", "find", "retrieval", "query", "keyword", "ocr", "receipt",
                             "memory", "remember", "scroll"],
            "Face Tagging": ["face", "tag", "pet", "cat", "dog", "tagging", "person", "grouped"],
            "Backup":       ["backup", "cellular", "wifi", "sync", "upload", "pause"],
            "UI Navigation":["confusing", "navigate", "layout", "where", "locked folder", "20 minutes",
                             "clicking", "moved"],
            "Editing":      ["edit", "trim", "video", "crop", "crash", "10 second", "clip"],
            "Albums":       ["album", "missing", "transfer", "structure", "iphone"],
        }

        for review in reviews:
            text_lower = review.text.lower()

            # Classify failure stage - assign the first matching stage
            assigned_stage = None
            # Check Post-Execution first (most specific) then Execution, then Discovery
            for stage in ["Post-Execution", "Execution", "Discovery"]:
                kws = stage_keywords[stage]
                if any(kw in text_lower for kw in kws):
                    assigned_stage = stage
                    break
            if not assigned_stage:
                assigned_stage = "Execution"  # sensible default
            stage_counts[assigned_stage] = stage_counts.get(assigned_stage, 0) + 1

            # Classify themes - a review can match multiple themes
            matched_any_theme = False
            for theme, kws in theme_keywords.items():
                if any(kw in text_lower for kw in kws):
                    theme_counts[theme] = theme_counts.get(theme, 0) + 1
                    matched_any_theme = True

        sources_connected = len(set(r.source for r in reviews if r.source))
        source_breakdown = {}
        for r in reviews:
            if r.source:
                source_breakdown[r.source] = source_breakdown.get(r.source, 0) + 1

        failure_stages_list = [
            {"stage": k, "count": v}
            for k, v in sorted(stage_counts.items(), key=lambda x: -x[1])
        ]
        themes_list = [
            {"theme": k, "count": v}
            for k, v in sorted(theme_counts.items(), key=lambda x: -x[1])
        ]

        return JSONResponse({
            "total_reviews": len(reviews),
            "sources_connected": sources_connected,
            "cleaned_count": len(reviews),
            "failure_stages_count": len(failure_stages_list),
            "themes_count": len(themes_list),
            "source_breakdown": source_breakdown,
            "failure_stages": failure_stages_list,
            "themes": themes_list,
        })

    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/insights")
async def get_insights():
    """
    Returns the top 4 discovery insights dynamically extracted from the database.
    Each insight includes a real representative user quote.
    """
    try:
        from src.process.db import get_engine, get_session, ReviewMetadata
        engine = get_engine()
        session = get_session(engine)
        reviews = session.query(ReviewMetadata).all()

        theme_keywords = {
            "Search":       ["search", "find", "retrieval", "query", "keyword", "ocr", "receipt",
                             "memory", "remember", "scroll"],
            "Face Tagging": ["face", "tag", "pet", "cat", "dog", "tagging", "person", "grouped"],
            "Backup":       ["backup", "cellular", "wifi", "sync", "upload", "pause"],
            "UI Navigation":["confusing", "navigate", "layout", "where", "locked folder", "20 minutes",
                             "clicking", "moved"],
            "Editing":      ["edit", "trim", "video", "crop", "crash", "10 second", "clip"],
            "Albums":       ["album", "missing", "transfer", "structure", "iphone"],
        }
        
        # Count themes and collect longest quotes
        theme_data = {t: {"count": 0, "longest_quote": ""} for t in theme_keywords}
        for r in reviews:
            text_lower = r.text.lower()
            for theme, kws in theme_keywords.items():
                if any(kw in text_lower for kw in kws):
                    theme_data[theme]["count"] += 1
                    if len(r.text) > len(theme_data[theme]["longest_quote"]):
                        # Keep quote length reasonable for UI cards
                        if len(r.text) < 300:
                            theme_data[theme]["longest_quote"] = r.text
        
        top_themes = sorted(theme_data.items(), key=lambda x: -x[1]["count"])[:4]
        
        insights = []
        for theme, data in top_themes:
            # Fallback text if no review matched length criteria
            quote = data['longest_quote'] or f"Multiple users reported {theme.lower()} issues."
            
            insights.append({
                "title": f"{theme} Issues",
                "summary": f"Users are struggling with {theme.lower()} according to {data['count']} user reviews.",
                "quote": quote,
                "review_count": data['count'],
                "theme_tag": theme
            })
            
        return JSONResponse(insights)

    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Accepts a user question and runs it through the LangGraph Corrective-RAG
    agent. The agent validates the question, retrieves relevant reviews from
    ChromaDB, grades their relevance, generates a structured PM synthesis,
    and guards against hallucination before returning the final answer.
    """
    try:
        from src.process.agent import run_agent
        result = run_agent(request.question)
        return JSONResponse(result)

    except Exception as exc:
        return JSONResponse(
            {"error": str(exc), "answer": f"Agent error: {exc}", "sources": []},
            status_code=500,
        )
