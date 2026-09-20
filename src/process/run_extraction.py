import sys
from pathlib import Path
import argparse
import concurrent.futures

# Add root to pythonpath
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.process.db import get_engine, get_session, ReviewMetadata
from src.process import extract, vector_db
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_review(r, llm):
    try:
        insight = extract.extract_insights(r.text, llm)
        doc = f"Review: {r.text}\nFailure Stage Identified: {insight.failure_stage}"
        meta = {
            "source": r.source or "", 
            "failure_stage": insight.failure_stage or "None",
            "author": r.author or "Anonymous",
            "url": r.url or ""
        }
        return (r.id, doc, meta)
    except Exception as e:
        logging.error(f"Error extracting {r.id}: {e}")
        return None

def run_extraction_and_indexing(reset=False):
    engine = get_engine()
    session = get_session(engine)
    
    reviews = session.query(ReviewMetadata).all()
    logging.info(f"Found {len(reviews)} cleaned reviews in SQLite.")
    
    if not reviews:
        logging.warning("No reviews found! Did you run clean.py first?")
        return
        
    client = vector_db.get_chroma_client()
    
    if reset:
        logging.info("Reset flag provided. Deleting existing 'reviews' collection...")
        try:
            client.delete_collection("reviews")
        except Exception as e:
            logging.info(f"Collection might not exist yet: {e}")
            
    col = vector_db.get_or_create_collection(client)
    
    try:
        llm = extract.get_llm()
    except Exception as e:
        logging.error(f"Could not load LLM (Check API key): {e}")
        return
    
    logging.info(f"Extracting insights and vectorizing all {len(reviews)} reviews using concurrent workers...")
    
    docs = []
    metas = []
    ids = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_review, r, llm) for r in reviews]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(reviews)):
            result = future.result()
            if result:
                rid, doc, meta = result
                ids.append(rid)
                docs.append(doc)
                metas.append(meta)
            
    if docs:
        vector_db.add_documents(col, docs, metas, ids)
        logging.info("Indexing complete! Data is ready for Streamlit.")
    else:
        logging.warning("No documents extracted.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract insights and index into ChromaDB")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the ChromaDB collection")
    args = parser.parse_args()
    
    run_extraction_and_indexing(reset=args.reset)
