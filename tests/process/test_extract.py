import pytest
from unittest.mock import MagicMock, patch
from src.process.extract import extract_insights
from src.process.schema import ReviewExtraction, InsightClue, Workaround

@patch('src.process.extract.get_llm')
def test_extract_insights_success(mock_get_llm):
    """Test that the LangChain extraction correctly invokes structured output."""
    # Mock the LangChain LLM components
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()
    
    # Mock the expected return object from Gemini
    expected_result = ReviewExtraction(
        failure_stage="Execution",
        clues=[InsightClue(theme="Search", description="Search bar spins")],
        workarounds=[Workaround(description="Scroll manually", is_effective=False)]
    )
    mock_structured_llm.invoke.return_value = expected_result
    
    # Wire the mock LLM to return the structured LLM mock
    mock_llm.with_structured_output.return_value = mock_structured_llm
    
    # Execute
    result = extract_insights("I had to scroll manually because search is broken", llm=mock_llm)
    
    # Verify
    assert result.failure_stage == "Execution"
    assert len(result.clues) == 1
    assert result.clues[0].theme == "Search"
    mock_structured_llm.invoke.assert_called_once()

def test_extract_insights_error():
    """Test that the pipeline returns a safe fallback on API failure."""
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()
    
    # Simulate an API Timeout or Quota Error
    mock_structured_llm.invoke.side_effect = Exception("API Timeout")
    mock_llm.with_structured_output.return_value = mock_structured_llm
    
    result = extract_insights("Some text", llm=mock_llm)
    
    # Should safely fallback
    assert result.failure_stage == "None"
    assert len(result.clues) == 0
