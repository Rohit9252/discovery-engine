# Discovery Engine - Agent Instructions

*This file contains instructions specific to the Discovery Engine folder. For global rules, refer to the root `AGENTS.md`.*

## Tech Stack Requirements
When building or modifying the Discovery Engine, agents must strictly adhere to the following approved tech stack:
- **Language**: Python
- **Orchestration**: LangChain / LangGraph (for multi-step agentic workflows and chat capabilities)
- **Data Validation & Typing**: Pydantic / Pydantic AI
- **Data Processing**: Pandas
- **UI/Dashboard**: Streamlit
- **LLM/Vision Model**: Gemini 1.5 Pro / Flash (via Google AI Studio APIs)

## Development Guidelines
- Follow the loosely coupled, component-based architecture rule set in the root `AGENTS.md`. 
- Scrapers should be placed in dedicated modules and must handle pagination, rate limits, and errors robustly. No hardcoded or shortcut scraping.
- The data pipeline must enforce strict JSON schemas using Pydantic.
