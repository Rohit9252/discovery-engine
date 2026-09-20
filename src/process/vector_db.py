import chromadb
from pathlib import Path
import logging
from functools import lru_cache
from src.process.paths import VECTOR_DATABASE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@lru_cache(maxsize=1)
def get_chroma_client(db_path=None):
    """Initialize and return a persistent ChromaDB client."""
    db_path = Path(db_path).resolve() if db_path is not None else VECTOR_DATABASE
    db_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(db_path))
    return client

@lru_cache(maxsize=1)
def get_or_create_collection(client, collection_name="reviews"):
    """Get or create a ChromaDB collection. Uses default all-MiniLM-L6-v2 embeddings."""
    collection = client.get_or_create_collection(name=collection_name)
    return collection

def add_documents(collection, documents, metadatas, ids):
    """
    Add text documents and their metadata to the vector store.
    
    Args:
        collection: The ChromaDB collection.
        documents (list of str): The text (e.g. extracted clues) to embed.
        metadatas (list of dict): Metadata for filtering (e.g. source, failure_stage).
        ids (list of str): Unique IDs linking back to the SQLite database.
    """
    if not documents:
        logging.warning("No documents to add to ChromaDB.")
        return
        
    collection.upsert(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    logging.info(f"Added {len(documents)} documents to ChromaDB collection '{collection.name}'.")

if __name__ == "__main__":
    client = get_chroma_client()
    col = get_or_create_collection(client)
    logging.info(f"Initialized ChromaDB with collection: {col.name}")
