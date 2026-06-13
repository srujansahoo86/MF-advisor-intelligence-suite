from pydantic import BaseModel, Field
from typing import List, Optional

class Answer(BaseModel):
    """Output contract for the Phase 1 FAQ Chatbot."""
    text: str = Field(description="The factual answer to the query, max 3 sentences.")
    citation_links: List[str] = Field(description="List of source URLs used.")
    needs_clarification: bool = Field(default=False, description="True if the query is ambiguous.")
    clarification_questions: List[str] = Field(default_factory=list, max_length=3, description="Up to 3 clarifying questions.")
    is_safe: bool = Field(default=True, description="True unless query triggered a guardrail.")
    refusal_message: Optional[str] = Field(default=None, description="Message to return if is_safe is False.")

class TopTheme(BaseModel):
    """A recurring theme extracted from reviews."""
    theme_name: str
    description: str

class WeeklyPulse(BaseModel):
    """Output contract for the Phase 2 Weekly Pulse."""
    top_themes: List[TopTheme]
    user_quotes: List[str] = Field(min_length=1, description="Redacted user quotes.")
    key_observation: str = Field(description="Key observation from the week's data.")
    action_ideas: List[str] = Field(min_length=3, max_length=3, description="Exactly 3 action ideas.")
    word_count: int

class FeeExplainer(BaseModel):
    """Output contract for the Phase 2 Fee Explainer."""
    bullets: List[str] = Field(min_length=6, max_length=6, description="Exactly 6 plain-language bullets.")
    source_links: List[str] = Field(min_length=2, max_length=2, description="Exactly 2 official source links.")
    last_checked: str = Field(description="Date string in format 'Last checked: YYYY-MM-DD'.")

class Booking(BaseModel):
    """Output contract for the Phase 3 Voice Scheduler."""
    booking_code: str = Field(description="Unique code e.g. KV-B391.")
    topic: str
    date_time: str
    status: str = "CONFIRMED"
    top_theme: Optional[str] = None   # from latest_pulse — used in MCP email
    prep_notes: Optional[str] = None   # what to prepare for the call

class PendingAction(BaseModel):
    """Output contract for Phase 4 MCP Orchestration."""
    action_id: str
    tool_name: str
    payload: dict
    status: str = Field(default="PENDING", description="PENDING, APPROVED, or REJECTED")
