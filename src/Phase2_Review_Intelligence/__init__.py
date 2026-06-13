"""
Phase 2 — Review Intelligence & Weekly Pulse
============================================
Exposes the four core components of the review processing pipeline:

    ReviewProcessor  → load & PII-redact reviews.csv
    PulseGenerator   → produce WeeklyPulse from cleaned reviews
    FeeExplainer     → produce FeeExplainer for the top fee theme
    CorpusUpdater    → inject FeeExplainer into Phase 1 ChromaDB
"""

from .review_processor import ReviewProcessor
from .pulse_generator import PulseGenerator
from .fee_explainer import FeeExplainerGenerator
from .corpus_updater import CorpusUpdater

__all__ = [
    "ReviewProcessor",
    "PulseGenerator",
    "FeeExplainerGenerator",
    "CorpusUpdater",
]
