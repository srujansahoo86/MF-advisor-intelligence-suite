import pytest
import os
from src.Phase1_FAQ_Chatbot.rag_engine import RAGEngine

@pytest.fixture
def rag_engine():
    # Only run tests if GROQ_API_KEY is available in env
    if not os.getenv("GROQ_API_KEY"):
        pytest.skip("Skipping RAG tests because GROQ_API_KEY is not set.")
    return RAGEngine()

def test_guardrails_integration(rag_engine):
    """Test that the RAG engine fast-fails on guardrails."""
    ans = rag_engine.answer_query("Should I buy Parag Parikh Liquid Fund?")
    assert not ans.is_safe
    assert "AMFI" in ans.text
    assert len(ans.citation_links) == 0

def test_ambiguity_check(rag_engine):
    """Test that ambiguous queries return clarifying questions."""
    ans = rag_engine.answer_query("What is the exit load for the fund?")
    assert ans.needs_clarification is True
    assert len(ans.clarification_questions) > 0
    assert len(ans.clarification_questions) <= 3

def test_missing_info(rag_engine):
    """Test graceful degradation for missing information."""
    ans = rag_engine.answer_query("What is the exit load for the XYZ Non-Existent Space Fund?")
    # Depending on ambiguity check, it might ask for clarification or outright fail.
    if not ans.needs_clarification:
        assert "verified source for that" in ans.text.lower()
        assert len(ans.citation_links) == 0


def test_citation_links_are_urls(rag_engine):
    """Citations must be clickable source URLs, not raw PDF filenames."""
    ans = rag_engine.answer_query("What is the exit load for Parag Parikh Liquid Fund?")
    assert len(ans.citation_links) > 0
    for link in ans.citation_links:
        assert link.startswith("http"), f"Citation '{link}' is not a URL"


def test_enforce_sentence_limit_truncates_long_text():
    """Responses longer than 3 sentences must be truncated to enforce the spec's '<=3 sentences' rule."""
    long_text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    result = RAGEngine._enforce_sentence_limit(long_text, max_sentences=3)
    assert result == "First sentence. Second sentence. Third sentence."


def test_enforce_sentence_limit_passes_short_text_through():
    """Text within the sentence limit must be returned unchanged."""
    short_text = "Only one sentence here."
    result = RAGEngine._enforce_sentence_limit(short_text, max_sentences=3)
    assert result == short_text


def test_enforce_sentence_limit_handles_questions_and_exclamations():
    """Sentence splitting must handle '?' and '!' terminators, not just '.'."""
    text = "Is this safe? Yes it is! Here's why. And more detail follows here."
    result = RAGEngine._enforce_sentence_limit(text, max_sentences=3)
    assert result == "Is this safe? Yes it is! Here's why."
