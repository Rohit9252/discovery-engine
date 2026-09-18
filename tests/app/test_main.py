import pytest
from streamlit.testing.v1 import AppTest

def test_dashboard_renders_successfully():
    """
    Test that the Streamlit app loads without any runtime errors,
    and all primary UI components (Charts & Chat) render successfully.
    """
    # Initialize the Streamlit AppTest framework with relative path from this test file
    at = AppTest.from_file("../../src/app/main.py")
    
    # Run the app simulation
    at.run(timeout=10)
    
    # Assert no exceptions occurred during the run (e.g. missing modules, syntax errors)
    assert not at.exception
    
    # Verify Title is present
    assert at.title[0].value == "🔍 Google Photos Discovery Engine"
    
    # Verify subheaders for charts and chat are present
    subheaders = [sh.value for sh in at.subheader]
    assert "Failure Stages" in subheaders
    assert "Top Pain Point Themes" in subheaders
    assert "✨ AI Discovery Engine" in subheaders
    
    # Verify the chat input box exists
    assert at.chat_input[0] is not None
