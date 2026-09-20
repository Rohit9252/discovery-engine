"""Serve the research dashboard and its evidence browsing API."""
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.process.dashboard import build_dashboard
from src.process.db import (CsvImportLedger, Phase1CatalogRow, ReviewMetadata,
                            get_engine, get_session, init_db)
from src.process.paths import PROJECT_ROOT, REVIEW_DATABASE
from src.process.source_audit import active_reviews
from src.process.issue_dashboard import apply_issue_dashboard, issue_evidence_page
from typing import Literal

load_dotenv(PROJECT_ROOT / '.env')
logger = logging.getLogger(__name__)
@asynccontextmanager
async def research_lifespan(application):
    engine = get_engine()
    try:
        init_db(engine)
    finally:
        engine.dispose()
    yield


app = FastAPI(title='Discovery Engine API', version='baseline-1', lifespan=research_lifespan)
STATIC_DIR = Path(__file__).parent / 'static'
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


@app.get('/', include_in_schema=False)
def serve_index():
    return FileResponse(STATIC_DIR / 'index.html', headers={'Cache-Control': 'no-cache'})


@app.get('/favicon.ico', include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / 'favicon.svg')


@app.api_route('/api/health', methods=['GET', 'HEAD'])
def health():
    import os
    db_exists = REVIEW_DATABASE.exists()
    catalog_rows = 0
    db_error = None
    if db_exists:
        engine = get_engine()
        try:
            with get_session(engine) as session:
                catalog_rows = session.query(Phase1CatalogRow).filter_by(active=1).count()
        except Exception as exc:
            db_error = str(exc)
        finally:
            engine.dispose()
    return {
        'app': 'discovery-engine',
        'version': 'baseline-1',
        'database': str(REVIEW_DATABASE),
        'database_exists': db_exists,
        'catalog_rows': catalog_rows,
        'openai_configured': bool(os.getenv('OPENAI_API_KEY')),
        'db_error': db_error,
    }


def dashboard_response(section):
    engine = get_engine()
    try:
        with get_session(engine) as session:
            if session.query(Phase1CatalogRow.id).filter_by(active=1).first():
                from src.process.catalog_dashboard import catalog_snapshot
                return catalog_snapshot(session)[section]
            reviews = active_reviews(session).order_by(ReviewMetadata.id).all()
            response = apply_issue_dashboard(session, reviews, *build_dashboard(reviews))[section]
            if section == 0:
                response['stored_count'] = session.query(ReviewMetadata).count()
                response['excluded_count'] = response['stored_count'] - len(reviews)
                from sqlalchemy import func
                decisions = dict(session.query(CsvImportLedger.disposition, func.count(CsvImportLedger.row_id))
                                 .group_by(CsvImportLedger.disposition).all())
                response['csv_import'] = {
                    'positive_rows': sum(decisions.values()),
                    'imported': decisions.get('imported', 0),
                    'existing': decisions.get('existing', 0),
                    'held': decisions.get('held', 0),
                }
            return response
    except Exception:
        logger.exception('Cannot load dashboard evidence')
        return JSONResponse({'error': 'Feedback storage is unavailable. Check the project database and run the cleaning pipeline if it has not been initialized.'}, status_code=503)
    finally:
        engine.dispose()


@app.get('/api/data')
def get_chart_data():
    return dashboard_response(0)


@app.get('/api/insights')
def get_insights():
    return dashboard_response(1)


@app.get('/api/research/evidence')
def get_retrieval_evidence(category: Literal['all', 'direct_memory_issue', 'retrieval_issue'] = 'all',
                           offset: int = Query(default=0, ge=0), limit: int = Query(default=12, ge=1, le=50)):
    engine = get_engine()
    try:
        with get_session(engine) as session:
            if session.query(Phase1CatalogRow.id).filter_by(active=1).first():
                return {'total': 0, 'offset': offset, 'limit': limit,
                        'analysis_status': 'catalog_relevance_check_pending', 'records': []}
            reviews = active_reviews(session).order_by(ReviewMetadata.id).all()
            return issue_evidence_page(session, reviews, category, offset, limit)
    except Exception:
        logger.exception('Cannot load retrieval evidence')
        return JSONResponse({'error': 'Retrieval evidence storage is unavailable.'}, status_code=503)
    finally:
        engine.dispose()


@app.post('/api/chat')
def chat(request: ChatRequest):
    import os
    api_key = (os.getenv('OPENAI_API_KEY') or '').strip().strip('"').strip("'")
    if not api_key:
        return JSONResponse({
            'error': 'Chat is unavailable because OPENAI_API_KEY is not set on the server. Add it in Render Environment and redeploy.',
            'sources': [],
        }, status_code=503)
    # Ensure downstream ChatOpenAI sees a clean key (no quotes/whitespace from dashboard paste).
    os.environ['OPENAI_API_KEY'] = api_key
    if not REVIEW_DATABASE.exists():
        return JSONResponse({
            'error': f'Project database file is missing at {REVIEW_DATABASE}. Confirm reviews.db is on main and redeploy.',
            'sources': [],
        }, status_code=503)

    engine = get_engine()
    try:
        from src.process.issue_chat import answer_issue_question
        with get_session(engine) as session:
            if session.query(Phase1CatalogRow.id).filter_by(active=1).first():
                from src.process.catalog_chat import answer_catalog_question
                return answer_catalog_question(session, request.question)
            return answer_issue_question(session, request.question)
    except Exception as exc:
        logger.exception('Research chat failed')
        message = str(exc)
        lower = message.lower()
        if 'api_key' in lower or 'authentication' in lower or 'unauthorized' in lower or 'incorrect api key' in lower or 'invalid_api_key' in lower:
            detail = (
                'OpenAI rejected the API key. In Render Environment, open OPENAI_API_KEY, '
                'remove any quotes or spaces, confirm it is a valid sk- key from platform.openai.com, '
                'save, then Manual Deploy again.'
            )
        else:
            detail = f'Issue evidence search is unavailable. Check the project database. ({type(exc).__name__}: {message[:180]})'
        return JSONResponse({'error': detail, 'sources': []}, status_code=503)
    finally:
        engine.dispose()
