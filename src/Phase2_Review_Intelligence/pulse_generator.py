import json
import time
from typing import List, Dict

from langchain_groq import ChatGroq

from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.schemas import WeeklyPulse, TopTheme
from src.Phase0_Shared_Foundation.persistence import Persistence
from src.Phase2_Review_Intelligence.review_processor import ReviewProcessor


_PULSE_PROMPT_TEMPLATE = """\
You are a senior product analyst at a mutual fund investment platform.
Analyse the following {n} user reviews collected this week and produce a concise Weekly Product Pulse.

STRICT RULES:
1. The ENTIRE JSON response (all fields combined) must be 250 words or fewer.
2. Return ONLY valid JSON — no markdown fences, no preamble.
3. top_themes: between 2 and 4 items.
4. user_quotes: between 1 and 3 items. Quotes MUST be taken verbatim from the reviews below. Do NOT invent quotes.
5. action_ideas: EXACTLY 3 items — short, actionable, product-team-facing.
6. key_observation: exactly 1 sentence summarising the week's dominant signal.
7. word_count: count every word across all fields in this JSON and put the total here.
8. No PII — reviews are already redacted but double-check your quotes.

JSON Schema:
{{
  "top_themes": [
    {{"theme_name": "<name>", "description": "<1-sentence description>"}}
  ],
  "user_quotes": ["<verbatim quote 1>", ...],
  "key_observation": "<one sentence>",
  "action_ideas": ["<idea 1>", "<idea 2>", "<idea 3>"],
  "word_count": <integer>
}}

Reviews:
{formatted_reviews}
"""


class PulseGenerator:
    """
    Calls the Groq LLM to produce a structured WeeklyPulse from
    a list of PII-redacted review dicts.

    Output is validated against the WeeklyPulse Pydantic schema and
    persisted to SQLite under the key 'latest_pulse'.
    """

    def __init__(self):
        self.llm = ChatGroq(model_name=Config.LLM_MODEL, temperature=0.3)
        self.persistence = Persistence()

    def generate(self, reviews: List[Dict]) -> WeeklyPulse:
        """
        Generate a WeeklyPulse from a list of clean review dicts.

        Retries once with a tighter word-limit reminder if the first
        response exceeds 250 words.

        Args:
            reviews: Output of ReviewProcessor.load() — PII already redacted.

        Returns:
            WeeklyPulse pydantic object.
        """
        processor = ReviewProcessor()
        formatted = processor.format_for_llm(reviews)
        prompt = _PULSE_PROMPT_TEMPLATE.format(
            n=len(reviews),
            formatted_reviews=formatted,
        )

        pulse = self._call_and_parse(prompt)

        # Retry once if over the word limit
        if pulse.word_count > 250:
            retry_prompt = (
                prompt
                + "\n\nIMPORTANT: Your previous response was over 250 words. "
                "Shorten all descriptions. Stay under 250 words total."
            )
            pulse = self._call_and_parse(retry_prompt)

        # Persist for Phase 3 & 4 to reference the top theme dynamically
        self.persistence.set("latest_pulse", pulse.model_dump())

        return pulse

    def _call_and_parse(self, prompt: str) -> WeeklyPulse:
        """Call the LLM and parse the JSON response into a WeeklyPulse.
        
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
                        print(f"[PulseGenerator] Rate limit hit, retrying in {wait_secs}s...")
                        time.sleep(wait_secs)
                        wait_secs *= 2
                        continue
                raise

        # Strip accidental markdown fences if the LLM ignored the instruction
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        # Normalise top_themes into TopTheme objects if they're plain dicts
        top_themes = [
            TopTheme(**t) if isinstance(t, dict) else t
            for t in data.get("top_themes", [])
        ]
        data["top_themes"] = top_themes

        return WeeklyPulse(**data)
