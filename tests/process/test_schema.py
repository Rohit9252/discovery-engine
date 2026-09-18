import pytest
from src.process.schema import ReviewExtraction
from pydantic import ValidationError

def test_review_extraction_schema_valid():
    """Test that valid JSON maps perfectly to the Pydantic model."""
    data = {
        "failure_stage": "Discovery",
        "clues": [
            {"theme": "Search", "description": "Search bar is broken"}
        ],
        "workarounds": []
    }
    
    obj = ReviewExtraction(**data)
    assert obj.failure_stage == "Discovery"
    assert len(obj.clues) == 1
    assert obj.clues[0].theme == "Search"
    assert len(obj.workarounds) == 0

def test_review_extraction_schema_invalid():
    """Test that Pydantic enforces required fields (missing failure_stage)."""
    with pytest.raises(ValidationError):
        ReviewExtraction(clues=[])
