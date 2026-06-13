import json
import time
from datetime import date
from typing import List, Dict

from langchain_groq import ChatGroq

from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.schemas import FeeExplainer
from src.Phase0_Shared_Foundation.persistence import Persistence
from src.Phase2_Review_Intelligence.review_processor import ReviewProcessor


# Keywords used to filter fee-related reviews from the full set
_FEE_KEYWORDS = [
    "expense ratio", "ter", "total expense ratio",
    "exit load", "stamp duty", "fee", "charge", "deduction",
    "hidden charge", "cost", "direct plan", "regular plan",
]

_FEE_PROMPT_TEMPLATE = """\
You are a SEBI-compliant financial educator writing for first-time mutual fund investors in India.

Based on the user confusion expressed in the reviews below, write a plain-language fee explainer.

STRICT RULES:
1. Return ONLY valid JSON — no markdown fences, no preamble.
2. bullets: EXACTLY 6 items. Each bullet must be one clear sentence, ≤ 25 words.
3. source_links: EXACTLY 2 items — use ONLY the two URLs provided below. Do not invent URLs.
4. last_checked: use EXACTLY the format "Last checked: {today}".
5. Neutral, jargon-free tone. No investment advice. No performance claims.
6. Do NOT include any PII. Reviews are already redacted.

Official source URLs (use both, in this order):
1. {amfi_url}
2. {sebi_url}

JSON Schema:
{{
  "bullets": [
    "<bullet 1>",
    "<bullet 2>",
    "<bullet 3>",
    "<bullet 4>",
    "<bullet 5>",
    "<bullet 6>"
  ],
  "source_links": ["{amfi_url}", "{sebi_url}"],
  "last_checked": "Last checked: {today}"
}}

Fee-related user reviews:
{fee_reviews}
"""


class FeeExplainerGenerator:
    """
    Identifies fee-confused reviews and calls the Groq LLM to produce
    a structured FeeExplainer with exactly 6 bullets and 2 official source links.

    Output is validated against the FeeExplainer Pydantic schema and
    persisted to SQLite under the key 'latest_fee_explainer'.
    """

    def __init__(self):
        self.llm = ChatGroq(model_name=Config.LLM_MODEL, temperature=0.1)
        self.persistence = Persistence()

    def generate(self, reviews: List[Dict]) -> FeeExplainer:
        """
        Filter fee-related reviews and generate the FeeExplainer.

        Args:
            reviews: Output of ReviewProcessor.load() — PII already redacted.

        Returns:
            FeeExplainer pydantic object.
        """
        # Filter to fee-related reviews; fall back to all reviews if none match
        processor = ReviewProcessor()
        fee_reviews = processor.get_by_theme_keywords(reviews, _FEE_KEYWORDS)
        if not fee_reviews:
            fee_reviews = reviews

        formatted = processor.format_for_llm(fee_reviews)
        today_str = date.today().isoformat()

        prompt = _FEE_PROMPT_TEMPLATE.format(
            today=today_str,
            amfi_url=Config.FEE_EXPLAINER_AMFI_URL,
            sebi_url=Config.FEE_EXPLAINER_SEBI_URL,
            fee_reviews=formatted,
        )

        explainer = self._call_and_parse(prompt, today_str)

        # Persist for Phase 1 corpus refresh and Phase 4 MCP
        self.persistence.set("latest_fee_explainer", explainer.model_dump())

        return explainer

    def _call_and_parse(self, prompt: str, today_str: str) -> FeeExplainer:
        """Call the LLM and parse the JSON response into a FeeExplainer.
        
        Retries up to 3 times with exponential backoff on rate limit (429) errors.
        """
        max_retries = 3
        wait_secs = 2

        for attempt in range(max_retries):
            try:
                raw = self.llm.invoke(prompt).content.strip()
                break  # success
            except Exception as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    if attempt < max_retries - 1:
                        print(f"[FeeExplainer] Rate limit hit, retrying in {wait_secs}s...")
                        time.sleep(wait_secs)
                        wait_secs *= 2  # exponential backoff: 2s → 4s → 8s
                        continue
                raise  # re-raise if not a rate limit error or exhausted retries

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        # Enforce the official source links regardless of what LLM returned
        data["source_links"] = [
            Config.FEE_EXPLAINER_AMFI_URL,
            Config.FEE_EXPLAINER_SEBI_URL,
        ]

        # Enforce last_checked format
        data["last_checked"] = f"Last checked: {today_str}"

        # Enforce exactly 6 bullets (truncate if LLM gave more)
        bullets = data.get("bullets", [])
        if len(bullets) > 6:
            data["bullets"] = bullets[:6]

        return FeeExplainer(**data)
