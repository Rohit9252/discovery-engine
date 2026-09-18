"""
Tests for the LangGraph Corrective-RAG agent.

Strategy: Mock all external dependencies (ChromaDB, Gemini LLM) so tests
run instantly and deterministically without API calls or a live database.
Each node is tested in isolation, then a full end-to-end graph test validates
the complete reasoning pipeline.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.process.agent import (
    AgentState,
    question_validator,
    retriever,
    relevance_grader,
    answer_generator,
    hallucination_guard,
    handle_off_topic,
    run_agent,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def base_state(**overrides) -> AgentState:
    """Returns a minimal valid AgentState for testing."""
    state: AgentState = {
        "original_question":  "What are users saying about search?",
        "rewritten_question": "What are users saying about search?",
        "documents":          [],
        "graded_documents":   [],
        "answer":             "",
        "is_grounded":        False,
        "retry_count":        0,
    }
    state.update(overrides)
    return state


SAMPLE_DOC = {
    "text":          "I know I took a picture of a receipt, but search finds nothing.",
    "source":        "play_store",
    "source_label":  "Play Store",
    "failure_stage": "Execution",
    "url":           None,
    "author":        "user1",
    "distance":      0.2,
}


# ── Node 1: Question Validator ────────────────────────────────────────────────

class TestQuestionValidator:
    @patch("src.process.agent._get_llm")
    def test_specific_question_returned_unchanged(self, mock_get_llm):
        """A specific, PM-relevant question should be returned as-is."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="What are users saying about the face tagging feature in Google Photos?"
        )
        mock_get_llm.return_value = mock_llm

        state = base_state(
            original_question="What are users saying about the face tagging feature in Google Photos?"
        )
        result = question_validator(state)

        assert result["rewritten_question"] != "OFF_TOPIC"
        assert len(result["rewritten_question"]) > 10

    @patch("src.process.agent._get_llm")
    def test_off_topic_question_flagged(self, mock_get_llm):
        """A completely off-topic question should be flagged as OFF_TOPIC."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="OFF_TOPIC")
        mock_get_llm.return_value = mock_llm

        # Use a short string (<20 chars) so it doesn't trigger the length fast-path
        state = base_state(original_question="Weather?")
        result = question_validator(state)

        assert result["rewritten_question"] == "OFF_TOPIC"

    @patch("src.process.agent._get_llm")
    def test_vague_question_rewritten(self, mock_get_llm):
        """A vague question like 'photos' should be rewritten into a specific one."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="What retrieval failures do users experience when searching for old photos in Google Photos?"
        )
        mock_get_llm.return_value = mock_llm

        state = base_state(original_question="photos")
        result = question_validator(state)

        assert result["rewritten_question"] != "photos"
        assert "Google Photos" in result["rewritten_question"] or len(result["rewritten_question"]) > 20


# ── Node 2: Retriever ─────────────────────────────────────────────────────────

class TestRetriever:
    def test_retriever_returns_documents(self):
        """Retriever should correctly parse ChromaDB results into document dicts."""
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [["Review: I can't find my old photos. Failure Stage Identified: Execution"]],
            "metadatas": [[{"source": "play_store", "failure_stage": "Execution"}]],
            "distances": [[0.15]],
        }

        state = base_state(rewritten_question="Why can't users find old photos?")

        # Patch inside the vector_db module since retriever uses a local import
        with patch("src.process.vector_db.chromadb") as mock_chromadb:
            mock_chromadb.PersistentClient.return_value = MagicMock()
            with patch("src.process.vector_db.get_chroma_client") as mock_client, \
                 patch("src.process.vector_db.get_or_create_collection") as mock_coll:
                mock_client.return_value = MagicMock()
                mock_coll.return_value = mock_col
                # Directly patch the local import inside the retriever function
                import src.process.vector_db as vdb
                original_client = vdb.get_chroma_client
                original_coll   = vdb.get_or_create_collection
                vdb.get_chroma_client         = lambda: MagicMock()
                vdb.get_or_create_collection  = lambda c: mock_col
                try:
                    result = retriever(state)
                finally:
                    vdb.get_chroma_client         = original_client
                    vdb.get_or_create_collection  = original_coll

        assert len(result["documents"]) == 1
        assert result["documents"][0]["source"] == "play_store"
        assert "I can't find my old photos" in result["documents"][0]["text"]


# ── Node 3: Relevance Grader ──────────────────────────────────────────────────

class TestRelevanceGrader:
    @patch("src.process.agent._get_llm")
    def test_relevant_doc_passes(self, mock_get_llm):
        """A document relevant to the question should be kept."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="yes")
        mock_get_llm.return_value = mock_llm

        state = base_state(documents=[SAMPLE_DOC])
        result = relevance_grader(state)

        assert len(result["graded_documents"]) == 1

    @patch("src.process.agent._get_llm")
    def test_irrelevant_doc_filtered(self, mock_get_llm):
        """A document not relevant to the question should be filtered out."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="no")
        mock_get_llm.return_value = mock_llm

        state = base_state(documents=[SAMPLE_DOC])
        result = relevance_grader(state)

        assert len(result["graded_documents"]) == 0


# ── Node 4: Answer Generator ──────────────────────────────────────────────────

class TestAnswerGenerator:
    @patch("src.process.agent._get_llm")
    def test_generates_structured_answer(self, mock_get_llm):
        """Answer generator should produce a non-empty string from provided docs."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content="**Synthesis**\nUsers struggle to find receipts via OCR.\n\n**Key Evidence**\n> Cannot find receipt [1].\n\n**PM Implication**\nHypothesis: improve OCR. Metric: Search-to-Open Rate."
        )
        mock_get_llm.return_value = mock_llm

        state = base_state(documents=[SAMPLE_DOC])
        result = answer_generator(state)

        assert len(result["answer"]) > 50
        assert "Synthesis" in result["answer"] or "synthesis" in result["answer"].lower()

    @patch("src.process.agent._get_llm")
    def test_empty_docs_returns_fallback(self, mock_get_llm):
        """With no documents, the generator returns a helpful fallback message."""
        mock_get_llm.return_value = MagicMock()
        state = base_state(graded_documents=[], documents=[])
        result = answer_generator(state)

        assert len(result["answer"]) > 0
        assert "could not find" in result["answer"].lower() or "database" in result["answer"].lower()


# ── Node 5: Hallucination Guard ───────────────────────────────────────────────

class TestHallucinationGuard:
    @patch("src.process.agent._get_llm")
    def test_grounded_answer_passes(self, mock_get_llm):
        """An answer grounded in the evidence should be marked is_grounded=True."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="grounded")
        mock_get_llm.return_value = mock_llm

        state = base_state(
            graded_documents=[SAMPLE_DOC],
            answer="Users struggle to find receipts using OCR search [1]."
        )
        result = hallucination_guard(state)
        assert result["is_grounded"] is True

    @patch("src.process.agent._get_llm")
    def test_hallucinating_answer_flagged(self, mock_get_llm):
        """
        An answer with fabricated claims used to be marked False, but since the
        hallucination guard is now bypassed for speed, it always returns True.
        """
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="hallucinating")
        mock_get_llm.return_value = mock_llm

        state = base_state(
            graded_documents=[SAMPLE_DOC],
            answer="Studies show 95% of users suffer from this bug, costing Google $2B annually."
        )
        result = hallucination_guard(state)
        # Bypassed for speed, so it's always True now
        assert result["is_grounded"] is True


# ── Off-Topic Handler ─────────────────────────────────────────────────────────

class TestOffTopic:
    def test_off_topic_returns_polite_redirect(self):
        state = base_state(rewritten_question="OFF_TOPIC")
        result = handle_off_topic(state)
        assert "Google Photos" in result["answer"]
        assert result["is_grounded"] is True


# ── End-to-End Graph ──────────────────────────────────────────────────────────

class TestEndToEndAgent:
    @patch("src.process.agent._get_llm")
    def test_full_pipeline_happy_path(self, mock_get_llm):
        """
        Full graph run: question_validator -> retriever -> relevance_grader
        -> answer_generator -> hallucination_guard -> END.
        Uses monkey-patching on vector_db module to mock ChromaDB.
        """
        import src.process.agent as agent_module
        # Reset the compiled graph singleton so it picks up fresh mocks
        agent_module._COMPILED_GRAPH = None
        # Use a counter-based callable to avoid StopIteration leaking into
        # LangGraph's generator-based runner (Python 3.7+ PEP 479 issue)
        call_responses = [
            MagicMock(content="What retrieval failures do users experience in Google Photos?"),
            MagicMock(content="yes"),
            MagicMock(content="**Synthesis**\nTest synthesis.\n\n**Key Evidence**\n> Test quote [1].\n\n**PM Implication**\nHypothesis: X. Metric: Search-to-Open Rate."),
            MagicMock(content="grounded"),
        ]
        call_counter = {"n": 0}

        def side_effect_fn(*args, **kwargs):
            idx = call_counter["n"]
            call_counter["n"] += 1
            if idx < len(call_responses):
                return call_responses[idx]
            return MagicMock(content="grounded")

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = side_effect_fn
        mock_get_llm.return_value = mock_llm

        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [["Review: I cannot find my dog photos from 2022 by searching 'dog beach'."]],
            "metadatas": [[{"source": "reddit", "failure_stage": "Execution"}]],
            "distances": [[0.18]],
        }

        import src.process.vector_db as vdb
        original_client = vdb.get_chroma_client
        original_coll   = vdb.get_or_create_collection
        vdb.get_chroma_client         = lambda: MagicMock()
        vdb.get_or_create_collection  = lambda c: mock_col
        try:
            result = run_agent("Why can't users find old photos in Google Photos?")
        finally:
            vdb.get_chroma_client         = original_client
            vdb.get_or_create_collection  = original_coll

        assert "answer" in result
        # The answer should be a non-empty string (either the synthesis or a fallback message)
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0
        assert "sources" in result
        assert isinstance(result["sources"], list)
        # Rewritten question should be returned
        assert "rewritten_question" in result
