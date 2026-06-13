from datetime import datetime, timedelta, date
from typing import Optional

from langchain_groq import ChatGroq
from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.persistence import Persistence

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class SlotManager:
    """Manages advisor appointment slots and resolves fuzzy user slot preferences."""

    def __init__(self, db_path: str = None):
        self.persistence = Persistence(db_path)
        self.llm = ChatGroq(model_name=Config.LLM_MODEL, temperature=0.0)

    def _occurrence_date(self, slot_label: str) -> str:
        """Computes the ISO date (YYYY-MM-DD) of the next upcoming occurrence
        of a '<Weekday> <H:MM AM/PM>' slot label, relative to now."""
        weekday_name, time_str = slot_label.split(" ", 1)
        target_weekday = _WEEKDAYS.index(weekday_name)
        slot_time = datetime.strptime(time_str, "%I:%M %p").time()

        now = datetime.now()
        days_ahead = (target_weekday - now.weekday()) % 7
        if days_ahead == 0 and now.time() >= slot_time:
            days_ahead = 7
        return (now + timedelta(days=days_ahead)).date().isoformat()

    def get_booked_slots(self) -> list[dict]:
        """Retrieves booked slots from SQLite as a list of {"slot", "date"}
        entries, pruning any whose occurrence date has already passed and
        discarding any legacy (pre-rolling) flat-string entries."""
        booked = self.persistence.get("booked_slots")
        if not booked or not isinstance(booked, list):
            return []

        today = date.today().isoformat()
        valid = [
            b for b in booked
            if isinstance(b, dict) and b.get("date", "") >= today
        ]
        if valid != booked:
            self.persistence.set("booked_slots", valid)
        return valid

    def is_available(self, slot: str) -> bool:
        """Returns True if the slot's next upcoming occurrence is currently free."""
        return not any(b["slot"] == slot for b in self.get_booked_slots())

    def mark_booked(self, slot: str) -> None:
        """Marks a slot's next upcoming occurrence as booked in SQLite."""
        booked = self.get_booked_slots()
        if not any(b["slot"] == slot for b in booked):
            booked.append({"slot": slot, "date": self._occurrence_date(slot)})
            self.persistence.set("booked_slots", booked)

    def release_slot(self, slot: str) -> None:
        """Releases a slot, making its next upcoming occurrence available again."""
        booked = self.get_booked_slots()
        filtered = [b for b in booked if b["slot"] != slot]
        if filtered != booked:
            self.persistence.set("booked_slots", filtered)

    def get_available_slots(self) -> list[str]:
        """Returns list of slot labels whose next upcoming occurrence is not yet booked."""
        booked_labels = {b["slot"] for b in self.get_booked_slots()}
        return [s for s in Config.AVAILABLE_SLOTS if s not in booked_labels]

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
