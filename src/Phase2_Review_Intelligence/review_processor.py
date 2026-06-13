import csv
import os
from typing import List, Dict

from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.pii import redact_pii


class ReviewProcessor:
    """
    Loads reviews from a CSV file, redacts PII from each review text,
    and returns a clean list of review dicts ready for LLM processing.

    PII is redacted at load-time — no downstream module ever touches
    raw personal data.

    CSV expected columns: review_id, date, rating, source, review_text
    """

    def __init__(self, csv_path: str = None):
        self.csv_path = csv_path or Config.REVIEWS_CSV_PATH

    def load(self) -> List[Dict]:
        """
        Reads the CSV, redacts PII in review_text, and returns
        a list of dicts with an added 'review_text_clean' key.

        Returns:
            List of dicts: {review_id, date, rating, source,
                            review_text_clean}
        """
        if not os.path.exists(self.csv_path):
            raise FileNotFoundError(
                f"Reviews CSV not found at: {self.csv_path}\n"
                "Run: copy reviews.csv data/reviews.csv"
            )

        reviews = []
        with open(self.csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                clean_text = redact_pii(row.get('review_text', ''))
                reviews.append({
                    'review_id':        row.get('review_id', ''),
                    'date':             row.get('date', ''),
                    'rating':           int(row.get('rating', 0)),
                    'source':           row.get('source', ''),
                    'review_text_clean': clean_text,
                })

        return reviews

    def get_low_rated(self, reviews: List[Dict], threshold: int = 3) -> List[Dict]:
        """Returns reviews with rating strictly below the threshold."""
        return [r for r in reviews if r['rating'] < threshold]

    def get_by_theme_keywords(
        self, reviews: List[Dict], keywords: List[str]
    ) -> List[Dict]:
        """Returns reviews whose text contains at least one of the keywords."""
        keywords_lower = [k.lower() for k in keywords]
        return [
            r for r in reviews
            if any(kw in r['review_text_clean'].lower() for kw in keywords_lower)
        ]

    def format_for_llm(self, reviews: List[Dict], max_reviews: int = 42) -> str:
        """
        Formats a list of clean reviews into a numbered string
        suitable for inclusion in an LLM prompt.
        """
        selected = reviews[:max_reviews]
        lines = []
        for i, r in enumerate(selected, start=1):
            lines.append(
                f"{i}. [{r['review_id']}] {r['rating']}★ ({r['source']}, {r['date']}): "
                f"{r['review_text_clean']}"
            )
        return "\n".join(lines)
