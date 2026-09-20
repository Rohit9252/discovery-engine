"""LLM-powered interactive chatbot for the Phase 1 catalog."""
import html
import re
import json
from collections import Counter
from typing import List

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.process.catalog_dashboard import SYMPTOM_NAMES
from src.process.catalog_schema import CatalogAssessment
from src.process.catalog_store import current_catalog_assessments
from src.process.db import Phase1CatalogRow


STOPWORDS = {
    'a', 'about', 'an', 'and', 'are', 'can', 'do', 'does', 'for', 'from', 'google',
    'how', 'in', 'is', 'issue', 'issues', 'of', 'on', 'photo', 'photos', 'problem',
    'problems', 'retrieval', 'search', 'the', 'their', 'there', 'to', 'user', 'users',
    'what', 'when', 'where', 'why', 'with', 'we', 'have', 'that', 'data', 'this',
    'even', 'though', 'their', 'they', 'them', 'it', 'its'
}


def get_llm():
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def source_entry(index, key, result, source):
    return {
        'index': index, 'id': key, 'source': source.source,
        'source_label': source.source.replace('_', ' ').title(),
        'url': source.url, 'snippet': (result.issue_quote or '')[:160],
        'full_text': source.text, 'failure_stage': result.issue_class,
    }


def terms(value):
    if not value:
        return set()
    return {word for word in re.findall(r'[a-z0-9]+', value.lower()) if len(word) > 2 and word not in STOPWORDS}


def answer_catalog_question(session, question):
    rows = session.query(Phase1CatalogRow).filter_by(active=1).order_by(Phase1CatalogRow.row_number).all()
    by_id = {row.id: row for row in rows}
    stored = current_catalog_assessments(session, rows)
    
    results = {}
    for key, item in stored.items():
        if item.status == 'succeeded':
            try:
                results[key] = CatalogAssessment.model_validate_json(item.result_json)
            except Exception:
                pass

    candidates = {key: result for key, result in results.items()
                  if by_id[key].source_type == 'existing_in_scope_evidence' and
                  result.issue_class in {'direct_memory_issue', 'observed_retrieval_issue'}}

    direct = sum(1 for result in candidates.values() if result.issue_class == 'direct_memory_issue')
    
    if not candidates:
        return {'answer': 'No source-backed retrieval issues have been classified yet.', 'sources': [], 'rewritten_question': question}

    # Extract keywords from user question to find relevant examples
    query_terms = terms(question)
    
    # Score candidates based on keyword overlap
    scored_candidates = []
    for key, result in candidates.items():
        source_row = by_id[key]
        if not source_row.url or not result.issue_quote:
            continue
            
        focused_text = ' '.join(filter(None, (
            result.issue_quote, 
            ' '.join(result.observed_symptoms),
            ' '.join(result.remembered_clues),
            ' '.join(result.target_media)
        )))
        
        # Give higher weight to matches in the direct tags/quotes, lower weight to the full source text
        score = 3 * len(query_terms & terms(focused_text)) + len(query_terms & terms(source_row.text))
        scored_candidates.append((score, key, result, source_row))

    # Sort by score descending
    scored_candidates.sort(key=lambda x: -x[0])
    
    context_lines = []
    used_urls = set()
    source_map = {}
    source_idx = 1
    
    # If there are specific keywords, take the top 15 highest-scoring relevant quotes
    if query_terms and scored_candidates and scored_candidates[0][0] > 0:
        for score, key, result, source_row in scored_candidates:
            if source_idx > 15:
                break
            if source_row.url not in used_urls:
                used_urls.add(source_row.url)
                quote = ' '.join((result.issue_quote or '').split())
                symptoms = ", ".join([SYMPTOM_NAMES.get(s, s) for s in result.observed_symptoms])
                context_lines.append(f"[{source_idx}] Symptoms: {symptoms} | Quote: \"{quote}\"")
                source_map[source_idx] = (key, result, source_row)
                source_idx += 1
    else:
        # Fallback to the diverse symptom sampler (broad questions like "what are the major reasons")
        symptoms_map = {}
        for key, result in candidates.items():
            for symptom in set(result.observed_symptoms):
                if symptom not in symptoms_map:
                    symptoms_map[symptom] = []
                symptoms_map[symptom].append((key, result))
    
        ranked = sorted(symptoms_map.items(), key=lambda item: (-len(item[1]), item[0]))
        
        for symptom, symptom_candidates in ranked[:5]:
            added_for_symptom = 0
            symptom_name = SYMPTOM_NAMES.get(symptom, symptom.replace('_', ' ').title())
            for key, result in symptom_candidates:
                if added_for_symptom >= 3:
                    break
                source_row = by_id[key]
                if source_row.url and source_row.url not in used_urls and result.issue_quote:
                    used_urls.add(source_row.url)
                    quote = ' '.join((result.issue_quote or '').split())
                    context_lines.append(f"[{source_idx}] Symptom: {symptom_name} | Quote: \"{quote}\"")
                    source_map[source_idx] = (key, result, source_row)
                    source_idx += 1
                    added_for_symptom += 1

    context_str = "\n".join(context_lines)
    
    system_prompt = f"""You are a product management research assistant for Google Photos.
Your job is to answer user questions about photo and video retrieval problems using ONLY the provided catalog data context.

### Overall Statistics (Do not share unless explicitly asked or highly relevant):
- Total catalog rows processed: {len(rows)}
- Number of real user reports detailing retrieval failures: {len(candidates)}
- Core opportunity (users who remembered a clue but forgot another detail and failed): {direct} cases

### Gathered Evidence Quotes (Specific to the user's question):
{context_str}

### Rules for your response:
1. Be conversational and helpful. Answer the user's specific question directly based ON THE QUOTES ABOVE.
2. NO JARGON. Do not use internal database terms (like 'observed_retrieval_issue', 'direct_memory_issue', etc.). Use plain English.
3. If the provided evidence doesn't perfectly answer the question, state what you CAN see from the data, but DO NOT say "the data does not mention..." if there is evidence above that mentions it! Look closely at the quotes!
4. CITE your sources using the bracketed numbers (e.g. [1], [2]) at the end of sentences when you quote or reference a user's experience.
5. Use Markdown for formatting (bullet points, bold text)."""

    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=question)
    ])
    
    answer = response.content
    
    # Extract which sources were actually cited by the LLM
    cited_indices = set(int(num) for num in re.findall(r'\[(\d+)\]', answer))
    
    sources = []
    # Re-number the sources sequentially (1, 2, 3...) for the UI, replacing them in the answer
    final_sources = []
    for old_idx in sorted(cited_indices):
        if old_idx in source_map:
            new_idx = len(final_sources) + 1
            # Replace [old_idx] with [new_idx] in the answer text
            answer = re.sub(rf'\[{old_idx}\]', f'[{new_idx}]', answer)
            key, result, source_row = source_map[old_idx]
            final_sources.append(source_entry(new_idx, key, result, source_row))
    
    return {'answer': answer, 'sources': final_sources, 'rewritten_question': question}
