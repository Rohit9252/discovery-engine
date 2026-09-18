import sys
from pathlib import Path

# Add root to pythonpath
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.process.db import get_engine, get_session, ReviewMetadata
from src.process import extract, vector_db
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_extraction_and_indexing():
    engine = get_engine()
    session = get_session(engine)
    
    reviews = session.query(ReviewMetadata).all()
    logging.info(f"Found {len(reviews)} cleaned reviews in SQLite.")
    
    if not reviews:
        logging.warning("No reviews found! Did you run clean.py first?")
        return
        
    client = vector_db.get_chroma_client()
    col = vector_db.get_or_create_collection(client)
    
    docs = []
    metas = []
    ids = []
    
    try:
        llm = extract.get_llm()
    except Exception as e:
        logging.error(f"Could not load LLM (Check API key): {e}")
        return
    
    # Process up to 50 for the MVP demo to save time and rate limits
    target_reviews = reviews[:50]
    logging.info(f"Extracting insights and vectorizing {len(target_reviews)} reviews...")
    
    for r in target_reviews:
        try:
            insight = extract.extract_insights(r.text, llm)
            # Combine text and the LLM's failure stage insight for the vector DB
            docs.append(f"Review: {r.text}\nFailure Stage Identified: {insight.failure_stage}")
            metas.append({"source": r.source, "failure_stage": insight.failure_stage})
            ids.append(r.id)
        except Exception as e:
            logging.error(f"Error extracting {r.id}: {e}")
            
    if docs:
        vector_db.add_documents(col, docs, metas, ids)
        logging.info("Indexing complete! Data is ready for Streamlit.")
    else:
        logging.warning("No documents extracted.")

if __name__ == "__main__":
    run_extraction_and_indexing()
