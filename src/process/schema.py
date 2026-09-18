from pydantic import BaseModel, Field
from typing import List

class InsightClue(BaseModel):
    """A specific clue or pain point extracted from a review."""
    theme: str = Field(..., description="The main theme of the clue, e.g., 'Face Recognition', 'Search', 'Backup'")
    description: str = Field(..., description="Detailed explanation of the issue or feature request.")
    
class Workaround(BaseModel):
    """A workaround the user employed to bypass the issue."""
    description: str = Field(..., description="How the user bypassed the issue.")
    is_effective: bool = Field(..., description="Does the workaround actually solve the problem?")

class ReviewExtraction(BaseModel):
    """
    The final structured output we expect Gemini 1.5 to return when analyzing a raw review.
    """
    failure_stage: str = Field(..., description="Where the user failed: 'Discovery', 'Execution', 'Post-Execution', or 'None'")
    clues: List[InsightClue] = Field(default_factory=list, description="List of clues extracted from the text.")
    workarounds: List[Workaround] = Field(default_factory=list, description="Any workarounds the user employed.")
