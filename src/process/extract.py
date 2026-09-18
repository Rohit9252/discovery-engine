import os
import logging
from langchain_openai import ChatOpenAI
from src.process.schema import ReviewExtraction

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_llm() -> ChatOpenAI:
    """Initialize and return the OpenAI LLM."""
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)

def extract_insights(text: str, llm=None) -> ReviewExtraction:
    """
    Use Gemini to extract structured insights (clues, workarounds, failure stage) 
    from raw review text using our Pydantic schema.
    """
    if llm is None:
        llm = get_llm()
        
    # Enforce Pydantic structured output
    structured_llm = llm.with_structured_output(ReviewExtraction)
    
    prompt = f"""
    Analyze the following user review/complaint for Google Photos.
    Extract the exact failure stage (Discovery, Execution, Post-Execution, or None), 
    any specific feature clues/themes, and any workarounds mentioned by the user.
    
    Review Text:
    {text}
    """
    
    try:
        logging.info(f"Calling Gemini for extraction on text length {len(text)}...")
        result = structured_llm.invoke(prompt)
        return result
    except Exception as e:
        logging.error(f"Extraction failed: {e}")
        # Return a safe fallback to prevent pipeline crashes
        return ReviewExtraction(failure_stage="None", clues=[], workarounds=[])

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    sample_text = "I can't figure out how to find my dog's pictures. The search bar just spins forever. I gave up and had to scroll manually for 10 minutes."
    result = extract_insights(sample_text)
    print(result.model_dump_json(indent=2))
