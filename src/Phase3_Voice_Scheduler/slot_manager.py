from typing import Optional

from langchain_groq import ChatGroq
from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.persistence import Persistence

class SlotManager:
    """Manages advisor appointment slots and resolves fuzzy user slot preferences."""

    def __init__(self, db_path: str = None):
        self.persistence = Persistence(db_path)
        self.llm = ChatGroq(model_name=Config.LLM_MODEL, temperature=0.0)

    def get_booked_slots(self) -> list[str]:
        """Retrieves list of booked slots from SQLite."""
        booked = self.persistence.get("booked_slots")
        if not booked or not isinstance(booked, list):
            return []
        return booked

    def is_available(self, slot: str) -> bool:
        """Returns True if the slot is currently free."""
        return slot not in self.get_booked_slots()

    def mark_booked(self, slot: str) -> None:
        """Marks a slot as booked in SQLite."""
        booked = self.get_booked_slots()
        if slot not in booked:
            booked.append(slot)
            self.persistence.set("booked_slots", booked)

    def release_slot(self, slot: str) -> None:
        """Releases a slot, making it available again."""
        booked = self.get_booked_slots()
        if slot in booked:
            booked.remove(slot)
            self.persistence.set("booked_slots", booked)

    def get_available_slots(self) -> list[str]:
        """Returns list of slots that are not yet booked."""
        booked = self.get_booked_slots()
        return [s for s in Config.AVAILABLE_SLOTS if s not in booked]

    def resolve(self, slot_preference: str | None) -> str:
        """
        Fuzzy matches slot_preference against available slots using an LLM.
        If slot_preference is None or empty, returns the first available slot.
        """
        available = self.get_available_slots()
        if not available:
            raise ValueError("No slots available.")

        if not slot_preference or not slot_preference.strip():
            return available[0]

        slots_str = "\n".join(available)
        prompt = f"""You are a slot matcher. Choose the exact slot string from the list below that best matches the user's slot preference.
If no slot is a reasonable match, or if it is ambiguous, choose the first slot from the list.
Return ONLY the exact matching slot string from the list. Do NOT return any other text, explanation, or markdown.

Available Slots:
{slots_str}

User Preference: "{slot_preference}"
"""
        try:
            response = self.llm.invoke(prompt).content.strip()
            # Clean up potential quotes or markdown
            response = response.replace('"', '').replace("'", "").strip()
            if response in available:
                return response
            
            # Secondary check: see if response is a substring of any available slot or vice-versa
            for slot in available:
                if slot.lower() in response.lower() or response.lower() in slot.lower():
                    return slot

            return available[0]
        except Exception:
            return available[0]

    def match_pending_reply(self, transcript: str) -> Optional[str]:
        """
        Matches a user's spoken reply to one of the currently available slots
        after the assistant asked "which slot works for you?".

        Unlike resolve(), this does NOT fall back to the first available slot
        when the reply doesn't clearly pick one — it returns None instead, so
        the caller can re-ask rather than silently booking an arbitrary slot
        (e.g. when the mic picks up noise, silence, or an echo of the
        assistant's own prompt instead of the user's actual choice).
        """
        available = self.get_available_slots()
        if not available or not transcript or not transcript.strip():
            return None

        slots_str = "\n".join(available)
        prompt = f"""The assistant just asked the user to pick one of these appointment slots:
{slots_str}

The user replied: "{transcript}"

If the reply clearly selects one of the slots above, return ONLY that exact slot string.
If the reply does not clearly select any of these slots (e.g. it's unrelated, unclear, silence, or a repeat of the assistant's own question), return exactly: NONE
Do NOT return any other text, explanation, or markdown.
"""
        try:
            response = self.llm.invoke(prompt).content.strip()
            response = response.replace('"', '').replace("'", "").strip()

            if response in available:
                return response

            if response.upper() == "NONE":
                return None

            # Secondary check: see if response is a substring of any available slot or vice-versa
            for slot in available:
                if slot.lower() in response.lower() or response.lower() in slot.lower():
                    return slot

            return None
        except Exception:
            return None
