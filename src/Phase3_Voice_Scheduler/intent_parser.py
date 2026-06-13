import json
from dataclasses import dataclass
from typing import Literal, Optional
from langchain_groq import ChatGroq
from src.Phase0_Shared_Foundation.config import Config

@dataclass
class ParsedIntent:
    intent: Literal["BOOK", "RESCHEDULE", "PREPARE", "OTHER"]
    topic: Optional[str] = None
    slot_preference: Optional[str] = None

class IntentParser:
    """Classifies user transcript and extracts topic/slot preferences."""

    def __init__(self):
        self.llm = ChatGroq(model_name=Config.LLM_MODEL, temperature=0.0)

    def parse(self, transcript: str) -> ParsedIntent:
        """
        Parses a transcript to identify the intent and parameters.
        Returns:
            ParsedIntent object.
        """
        if not transcript or not transcript.strip():
            return ParsedIntent(intent="OTHER", topic=None, slot_preference=None)

        prompt = f"""Classify the user's voice input for a mutual fund advisor booking system.
Return ONLY valid JSON:
{{
  "intent": "BOOK" | "RESCHEDULE" | "PREPARE" | "OTHER",
  "topic": "<topic string or null>",
  "slot_preference": "<slot hint string or null>"
}}
Rules:
- BOOK: user wants to book a new call (e.g. "I want to schedule/book a slot", "book an appointment", "connect with an advisor")
- RESCHEDULE: user wants to change an existing booking (e.g. "reschedule my slot", "move my appointment", "change my booking")
- PREPARE: user asks what to prepare for their call (e.g. "what do I need for the call?", "how should I prepare?", "checklist")
- OTHER: anything else (will receive a polite redirect)
- Do NOT invent slot times — extract only what the user said (e.g. "Friday afternoon", "Monday morning").
Transcript: "{transcript}"
"""
        try:
            response = self.llm.invoke(prompt).content.strip()
            
            # Extract JSON block between the first '{' and last '}' to handle explanations or markdown wrappers
            start_idx = response.find("{")
            end_idx = response.rfind("}")
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx+1]
            else:
                json_str = response
            
            data = json.loads(json_str)
            
            intent = data.get("intent", "OTHER")
            if intent not in ["BOOK", "RESCHEDULE", "PREPARE", "OTHER"]:
                intent = "OTHER"

            topic = data.get("topic")
            if not topic or str(topic).lower() in ["null", "none", ""]:
                topic = None
            else:
                topic = str(topic)

            slot_preference = data.get("slot_preference")
            if not slot_preference or str(slot_preference).lower() in ["null", "none", ""]:
                slot_preference = None
            else:
                slot_preference = str(slot_preference)

            return ParsedIntent(intent=intent, topic=topic, slot_preference=slot_preference)

        except Exception:
            # Fallback to OTHER on any parser failure
            return ParsedIntent(intent="OTHER", topic=None, slot_preference=None)
