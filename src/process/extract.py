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
    
    import time
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # We don't log every attempt unless it's a retry to avoid spamming the console
            if attempt > 0:
                logging.info(f"Retrying extraction... (Attempt {attempt+1}/{max_retries})")
            
            result = structured_llm.invoke(prompt)
            return result
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
                wait_time = (2 ** attempt) + 2  # 3s, 4s, 6s, 10s, 18s
                logging.warning(f"Rate limited (429). Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                logging.error(f"Extraction failed with non-retryable error: {e}")
                break
                
    # Return a safe fallback to prevent pipeline crashes if all retries fail
    logging.error("Max retries exceeded for extraction. Falling back to 'None'.")
    return ReviewExtraction(failure_stage="None", clues=[], workarounds=[])

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    sample_text = "I can't figure out how to find my dog's pictures. The search bar just spins forever. I gave up and had to scroll manually for 10 minutes."
    result = extract_insights(sample_text)
    print(result.model_dump_json(indent=2))
