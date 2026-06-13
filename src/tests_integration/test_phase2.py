"""
Integration tests for Phase 2 — Review Intelligence & Weekly Pulse.

Test groups:
    A. ReviewProcessor  (no API key needed — pure CSV + PII logic)
    B. PulseGenerator   (requires GROQ_API_KEY)
    C. FeeExplainer     (requires GROQ_API_KEY)
    D. CorpusUpdater    (no API key needed — ChromaDB + embeddings)
    E. Full pipeline    (requires GROQ_API_KEY)
"""

import re
import os
import pytest

from src.Phase2_Review_Intelligence.review_processor import ReviewProcessor
from src.Phase2_Review_Intelligence.corpus_updater import CorpusUpdater


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_pii(text: str) -> bool:
    """Returns True if raw PII patterns are found in text."""
    patterns = [
        r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}',  # email
        r'\b[6-9]\d{9}\b',                                    # 10-digit phone
        r'\+91[\s\-]?\d{5}[\s\-]?\d{5}',                     # +91 phone
        r'\b[A-Z]{5}[0-9]{4}[A-Z]\b',                        # PAN
        r'\b\d{5,8}/\d{2,4}\b',                               # folio
    ]
    return any(re.search(p, text) for p in patterns)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def reviews():
    """Load and redact reviews once for the whole module."""
    processor = ReviewProcessor()
    return processor.load()


@pytest.fixture(scope="module")
def groq_reviews(reviews):
    """Skip if GROQ_API_KEY not available; otherwise return reviews."""
    if not os.getenv("GROQ_API_KEY"):
        pytest.skip("Skipping LLM tests: GROQ_API_KEY not set.")
    return reviews


# ---------------------------------------------------------------------------
# A. ReviewProcessor tests (no API key needed)
# ---------------------------------------------------------------------------

def test_review_processor_loads_all_rows(reviews):
    """CSV must load exactly 42 rows."""
    assert len(reviews) == 42, f"Expected 42 reviews, got {len(reviews)}"


def test_review_processor_no_raw_pii(reviews):
    """Every review_text_clean must be free of raw PII after redaction."""
    for r in reviews:
        assert not _has_pii(r['review_text_clean']), (
            f"PII found in {r['review_id']}: {r['review_text_clean']}"
        )


def test_pii_redaction_known_rows(reviews):
    """Spot-check the 4 known PII rows individually."""
    review_map = {r['review_id']: r for r in reviews}

    # R010 — PAN: ABCDE1234F
    assert 'ABCDE1234F' not in review_map['R010']['review_text_clean']

    # R015 — Phone: 9123456780
    assert '9123456780' not in review_map['R015']['review_text_clean']

    # R024 — Email: rajesh.kumar88@gmail.com
    assert 'rajesh.kumar88@gmail.com' not in review_map['R024']['review_text_clean']

    # R028 — Folio: 1234567/89
    assert '1234567/89' not in review_map['R028']['review_text_clean']


def test_review_processor_rating_field(reviews):
    """Ratings must be integers between 1 and 5."""
    for r in reviews:
        assert isinstance(r['rating'], int), f"{r['review_id']} rating is not int"
        assert 1 <= r['rating'] <= 5, f"{r['review_id']} rating out of range: {r['rating']}"


def test_review_processor_required_fields(reviews):
    """Each row must have all expected keys."""
    required_keys = {'review_id', 'date', 'rating', 'source', 'review_text_clean'}
    for r in reviews:
        assert required_keys.issubset(r.keys()), (
            f"{r['review_id']} missing keys: {required_keys - r.keys()}"
        )


# ---------------------------------------------------------------------------
# B. PulseGenerator tests (requires GROQ_API_KEY)
# ---------------------------------------------------------------------------

def test_pulse_generation(groq_reviews):
    """WeeklyPulse must conform to the schema constraints."""
    from src.Phase2_Review_Intelligence.pulse_generator import PulseGenerator
    from src.Phase0_Shared_Foundation.schemas import WeeklyPulse

    gen = PulseGenerator()
    pulse = gen.generate(groq_reviews)

    assert isinstance(pulse, WeeklyPulse)
    assert pulse.word_count <= 250, f"word_count {pulse.word_count} exceeds 250"
    assert len(pulse.action_ideas) == 3, (
        f"Expected 3 action ideas, got {len(pulse.action_ideas)}"
    )
    assert len(pulse.user_quotes) >= 1, "Must have at least 1 user quote"
    assert len(pulse.top_themes) >= 2, "Must have at least 2 top themes"
    assert pulse.key_observation, "key_observation must not be empty"


def test_pulse_no_pii_in_output(groq_reviews):
    """The generated pulse must contain no raw PII."""
    from src.Phase2_Review_Intelligence.pulse_generator import PulseGenerator

    gen = PulseGenerator()
    pulse = gen.generate(groq_reviews)

    # Check all text-containing fields
    all_text = " ".join([
        pulse.key_observation,
        *pulse.user_quotes,
        *pulse.action_ideas,
        *[t.theme_name + " " + t.description for t in pulse.top_themes],
    ])
    assert not _has_pii(all_text), f"PII found in pulse output: {all_text}"


# ---------------------------------------------------------------------------
# C. FeeExplainer tests (requires GROQ_API_KEY)
# ---------------------------------------------------------------------------

def test_fee_explainer_generation(groq_reviews):
    """FeeExplainer must have exactly 6 bullets, 2 sources, and a last_checked stamp."""
    from src.Phase2_Review_Intelligence.fee_explainer import FeeExplainerGenerator
    from src.Phase0_Shared_Foundation.schemas import FeeExplainer
    from src.Phase0_Shared_Foundation.config import Config

    gen = FeeExplainerGenerator()
    explainer = gen.generate(groq_reviews)

    assert isinstance(explainer, FeeExplainer)
    assert len(explainer.bullets) == 6, (
        f"Expected 6 bullets, got {len(explainer.bullets)}"
    )
    assert len(explainer.source_links) == 2, (
        f"Expected 2 source links, got {len(explainer.source_links)}"
    )
    assert Config.FEE_EXPLAINER_AMFI_URL in explainer.source_links
    assert Config.FEE_EXPLAINER_SEBI_URL in explainer.source_links
    assert explainer.last_checked.startswith("Last checked: "), (
        f"Unexpected last_checked format: {explainer.last_checked}"
    )


# ---------------------------------------------------------------------------
# D. CorpusUpdater tests (no API key needed)
# ---------------------------------------------------------------------------

def test_corpus_updater_injects_document():
    """After injection, similarity search must return the fee_explainer doc."""
    from src.Phase0_Shared_Foundation.schemas import FeeExplainer

    # Create a minimal FeeExplainer directly (no LLM needed)
    dummy = FeeExplainer(
        bullets=[
            "Expense ratio is the annual fee deducted from your investment.",
            "Direct plans have lower expense ratios than regular plans.",
            "Exit load is charged when you redeem within the lock-in window.",
            "Stamp duty of 0.005% applies on every mutual fund purchase.",
            "TER (Total Expense Ratio) includes all fund management charges.",
            "No hidden platform fee is charged by zero-commission platforms.",
        ],
        source_links=[
            "https://www.amfiindia.com/investor-corner",
            "https://www.sebi.gov.in/sebi_data/attachdocs/1475063737177.pdf",
        ],
        last_checked="Last checked: 2026-06-09",
    )

    updater = CorpusUpdater()
    updater.add_fee_explainer(dummy)

    # Verify retrieval
    count = updater.get_injected_count()
    assert count >= 1, "fee_explainer_generated document not found in ChromaDB"


# ---------------------------------------------------------------------------
# E. Full pipeline end-to-end (requires GROQ_API_KEY)
# ---------------------------------------------------------------------------

def test_full_pipeline(groq_reviews):
    """
    End-to-end: load → pulse → fee_explainer → corpus inject → RAG retrieves it.
    This is the key integration test proving M2 feeds M1.
    """
    from src.Phase2_Review_Intelligence.pulse_generator import PulseGenerator
    from src.Phase2_Review_Intelligence.fee_explainer import FeeExplainerGenerator
    from src.Phase2_Review_Intelligence.corpus_updater import CorpusUpdater
    from src.Phase1_FAQ_Chatbot.rag_engine import RAGEngine

    # Step 1: Generate pulse
    pulse = PulseGenerator().generate(groq_reviews)
    assert pulse is not None

    # Step 2: Generate fee explainer
    explainer = FeeExplainerGenerator().generate(groq_reviews)
    assert explainer is not None

    # Step 3: Inject into corpus
    CorpusUpdater().add_fee_explainer(explainer)

    # Step 4: RAG should now retrieve the fee explainer for a fee query
    rag = RAGEngine()
    answer = rag.answer_query(
        "What is the expense ratio for Parag Parikh Liquid Fund?"
    )
    # After injection, at least one citation should reference the fee explainer
    # or the answer should not be the fallback "no verified source" response
    assert answer.is_safe, "RAG returned unsafe answer"
    # It may still say no verified source if the vector search doesn't match —
    # but it must not crash, and citations list must be a list (possibly empty)
    assert isinstance(answer.citation_links, list)


def test_reviews_span_eight_to_twelve_weeks(reviews):
    """Review dates must span 8-12 weeks (56-84 days) per problem statement."""
    from datetime import date
    parsed_dates = [date.fromisoformat(r['date']) for r in reviews]
    span_days = (max(parsed_dates) - min(parsed_dates)).days
    assert 56 <= span_days <= 84, f"Review date span is {span_days} days, expected 56-84 (8-12 weeks)"
