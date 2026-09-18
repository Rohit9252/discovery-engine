import pytest
from src.process.vector_db import get_chroma_client, get_or_create_collection, add_documents

def test_chromadb_initialization_and_insertion(tmp_path):
    """Test that ChromaDB properly initializes and can index/query documents."""
    db_path = tmp_path / "chroma"
    client = get_chroma_client(str(db_path))
    collection = get_or_create_collection(client, "test_col")
    
    assert collection.name == "test_col"
    
    # 1. Insert Document
    add_documents(
        collection=collection,
        documents=["The face recognition feature completely fails on my dog."],
        metadatas=[{"source": "play_store"}],
        ids=["doc_1"]
    )
    
    # 2. Query Document using semantic similarity
    results = collection.query(
        query_texts=["Issues with animal faces"], 
        n_results=1
    )
    
    # Verify the correct document was retrieved based on semantic meaning
    assert len(results["ids"]) > 0
    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "doc_1"
    assert results["documents"][0][0] == "The face recognition feature completely fails on my dog."
