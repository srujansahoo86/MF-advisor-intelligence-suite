import re
import random
import string
from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.persistence import Persistence
from src.Phase0_Shared_Foundation.schemas import Booking
from src.Phase1_FAQ_Chatbot.rag_engine import get_rag_engine

from .pii_deflector import PIIDeflector
from .intent_parser import IntentParser
from .slot_manager import SlotManager
from src.Phase4_MCP_Orchestration.orchestrator import MCPOrchestrator

_TIME_WORD_RE = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"\d{1,2}(:\d{2})?\s*(am|pm)|morning|afternoon|evening|noon|tonight)\b",
    re.IGNORECASE,
)


def _transcript_mentions_time(transcript: str) -> bool:
    """Returns True if the transcript contains a day-of-week or time-of-day word."""
    if not transcript:
        return False
    return bool(_TIME_WORD_RE.search(transcript))


_GOODBYE_RE = re.compile(
    r"\b(bye|goodbye|good bye|that'?s all|thats all|nothing else|"
    r"no(?:,)? (?:that'?s|thats) (?:all|it)|that'?s it|we'?re done|"
    r"i'?m done|end (?:the )?call|hang up)\b",
    re.IGNORECASE,
)


def _is_goodbye(transcript: str) -> bool:
    """Returns True if the transcript signals the user wants to end the call."""
    if not transcript:
        return False
    return bool(_GOODBYE_RE.search(transcript))


@dataclass
class AgentResponse:
    message: str
    booking: Optional[Booking] = None
    booking_code: Optional[str] = None
    top_theme: Optional[str] = None
    awaiting_response: bool = False
    session_ended: bool = False

class BookingAgent:
    """Orchestrates voice booking, rescheduling, and preparation help."""

    def __init__(self, db_path: str = None):
        self.persistence = Persistence(db_path)
        self.pii_deflector = PIIDeflector()
        self.intent_parser = IntentParser()
        self.slot_manager = SlotManager(db_path)
        self.orchestrator = MCPOrchestrator(db_path)

    def _generate_booking_code(self) -> str:
        """Generates a unique booking code in the format KV-XXXX."""
        while True:
            suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            code = f"KV-{suffix}"
            if self.persistence.get(code) is None:
                return code

    def _get_top_theme(self) -> Optional[str]:
        """Reads Phase 2's latest_pulse to inject the top theme into the greeting."""
        pulse = self.persistence.get("latest_pulse")
        if pulse and "top_themes" in pulse and len(pulse["top_themes"]) > 0:
            theme_obj = pulse["top_themes"][0]
            if isinstance(theme_obj, dict):
                return theme_obj.get("theme_name")
            elif hasattr(theme_obj, "theme_name"):
                return theme_obj.theme_name
        return None

    def _book_confirmation_message(self, slot: str, code: str, top_theme: Optional[str]) -> str:
        """Builds the confirmation message for a newly confirmed booking."""
        if top_theme:
            return (
                f"Many users are asking about {top_theme} this week — I can book a slot for that!\n"
                f"Your appointment is confirmed for {slot}. Your Booking Code is {code}.\n"
                "Please save it — you'll need it to reschedule or cancel."
            )
        return (
            f"Your appointment is confirmed for {slot}. Your Booking Code is {code}.\n"
            "Please save it — you'll need it to reschedule or cancel."
        )

    def _slot_list_text(self, available: list[str]) -> str:
        """Formats a list of available slots as a bulleted list."""
        return "\n".join(f"- {s}" for s in available)

    def _queue_calendar_hold(self, booking: Booking) -> None:
        """Queues a Calendar Hold Creator action for advisor approval."""
        self.orchestrator.queue_action("Calendar Hold Creator", {
            "title": f"Advisor Call: {booking.topic} ({booking.booking_code})",
            "start_time": booking.date_time,
            "duration_minutes": 30,
            "attendees": ["advisor@kuvera.in"],
        })

    def _queue_doc_append(self, booking: Booking, top_theme: Optional[str]) -> None:
        """Queues a Doc Append action logging this booking to the shared notes doc."""
        pulse = self.persistence.get("latest_pulse")
        fee_explainer = self.persistence.get("latest_fee_explainer")

        lines = [
            f"## {date.today().isoformat()} — Booking {booking.booking_code}",
            f"- Topic: {booking.topic}",
            f"- Slot: {booking.date_time}",
        ]
        if top_theme:
            lines.append(f"- Top Theme: {top_theme}")
        if pulse and pulse.get("key_observation"):
            lines.append(f"- Pulse Observation: {pulse['key_observation']}")
        if fee_explainer and fee_explainer.get("last_checked"):
            lines.append(f"- Fee Explainer: {fee_explainer['last_checked']}")
        lines.append("")

        self.orchestrator.queue_action("Doc Append", {
            "file_path": Config.SHARED_NOTES_PATH,
            "content": "\n".join(lines),
        })

    def _queue_email_draft(self, booking: Booking) -> None:
        """Queues an Email Draft Generator action for advisor approval."""
        self.orchestrator.queue_action("Email Draft Generator", {
            "recipient": "advisor@kuvera.in",
            "subject": f"Pre-meeting brief: {booking.topic} ({booking.booking_code})",
            "topic": booking.topic,
        })

    def _queue_mcp_followups(self, booking: Booking, top_theme: Optional[str]) -> None:
        """Queues all required MCP actions for a confirmed booking/reschedule."""
        self._queue_calendar_hold(booking)
        self._queue_doc_append(booking, top_theme)
        self._queue_email_draft(booking)

    def _finalize_pending_booking(self, pending: dict, transcript: str, top_theme: Optional[str]) -> AgentResponse:
        """Resolves the user's slot choice and completes a pending BOOK or RESCHEDULE."""
        new_slot = self.slot_manager.match_pending_reply(transcript)
        if new_slot is None:
            available = self.slot_manager.get_available_slots()
            if not available:
                self.persistence.set("pending_booking", {})
                return AgentResponse(message="No slots available.")

            # Reply didn't clearly pick one of the offered slots (e.g. noise,
            # silence, or an echo of the assistant's own prompt) — re-ask and
            # keep the pending booking open so the mic stays on until the
            # user actually chooses a slot.
            slot_list = self._slot_list_text(available)
            ask_message = (
                "Sorry, I didn't catch a valid slot choice.\n"
                f"Here are the available appointment slots:\n{slot_list}\n"
                "Which one works for you?"
            )
            return AgentResponse(message=ask_message, top_theme=top_theme, awaiting_response=True)

        self.slot_manager.mark_booked(new_slot)

        code = self._generate_booking_code()

        if pending["type"] == "RESCHEDULE":
            old_code = pending["code_to_reschedule"]
            self.slot_manager.release_slot(pending["old_slot"])

            old_booking_data = self.persistence.get(old_code)
            if old_booking_data:
                old_booking_data["status"] = "CANCELLED"
                self.persistence.set(old_code, old_booking_data)

            latest_b = self.persistence.get("latest_booking")
            if latest_b and latest_b.get("booking_code") == old_code:
                latest_b["status"] = "CANCELLED"
                self.persistence.set("latest_booking", latest_b)

            booking = Booking(
                booking_code=code,
                topic=pending["topic"],
                date_time=new_slot,
                status="CONFIRMED",
                top_theme=top_theme,
                prep_notes=pending.get("prep_notes")
            )
            self.persistence.set(code, booking.model_dump())
            self.persistence.set("latest_booking", booking.model_dump())
            self.persistence.set("pending_booking", {})
            self._queue_mcp_followups(booking, top_theme)

            message = (
                f"Your appointment has been rescheduled. Old booking {old_code} is cancelled. "
                f"Your new appointment is confirmed for {new_slot}. Your new Booking Code is {code}."
            )
            return AgentResponse(message=message, booking=booking, booking_code=code, top_theme=top_theme)

        # pending["type"] == "BOOK"
        booking = Booking(
            booking_code=code,
            topic=pending["topic"],
            date_time=new_slot,
            status="CONFIRMED",
            top_theme=top_theme,
            prep_notes=None
        )
        self.persistence.set(code, booking.model_dump())
        self.persistence.set("latest_booking", booking.model_dump())
        self.persistence.set("pending_booking", {})
        self._queue_mcp_followups(booking, top_theme)

        message = self._book_confirmation_message(new_slot, code, top_theme)
        return AgentResponse(message=message, booking=booking, booking_code=code, top_theme=top_theme)

    def handle(self, transcript: str) -> AgentResponse:
        """
        Coordinates the full booking process for a given transcript.
        """
        # 1. PIIDeflector check
        has_pii, pii_msg = self.pii_deflector.check(transcript)
        if has_pii:
            return AgentResponse(message=pii_msg)

        # 2. Goodbye check — ends the session regardless of any pending state,
        # so a user can escape a "which slot?" loop by saying "never mind, bye".
        if _is_goodbye(transcript):
            self.persistence.set("pending_booking", {})
            return AgentResponse(
                message="Thank you for calling Kuvera. Have a great day!",
                session_ended=True,
            )

        # 3. Retrieve top theme (if available)
        top_theme = self._get_top_theme()

        # 4. If a booking/reschedule is awaiting a slot choice, this transcript is the answer
        pending = self.persistence.get("pending_booking")
        if pending:
            return self._finalize_pending_booking(pending, transcript, top_theme)

        # 5. Parse Intent
        parsed = self.intent_parser.parse(transcript)

        # Guard against the LLM hallucinating a slot_preference when the user
        # never actually mentioned a day/time — force the ask-for-options flow.
        if parsed.slot_preference and not _transcript_mentions_time(transcript):
            parsed.slot_preference = None

        # 6. Handle Intents
        if parsed.intent == "BOOK":
            topic = parsed.topic or "General Consultation"

            if parsed.slot_preference:
                try:
                    slot = self.slot_manager.resolve(parsed.slot_preference)
                    self.slot_manager.mark_booked(slot)
                except ValueError as e:
                    return AgentResponse(message=str(e))

                code = self._generate_booking_code()
                booking = Booking(
                    booking_code=code,
                    topic=topic,
                    date_time=slot,
                    status="CONFIRMED",
                    top_theme=top_theme,
                    prep_notes=None
                )
                self.persistence.set(code, booking.model_dump())
                self.persistence.set("latest_booking", booking.model_dump())
                self._queue_mcp_followups(booking, top_theme)

                message = self._book_confirmation_message(slot, code, top_theme)
                return AgentResponse(message=message, booking=booking, booking_code=code, top_theme=top_theme)

            # No slot preference given — ask the user to choose before booking
            available = self.slot_manager.get_available_slots()
            if not available:
                return AgentResponse(message="No slots available.")

            self.persistence.set("pending_booking", {"type": "BOOK", "topic": topic})

            slot_list = self._slot_list_text(available)
            if top_theme:
                ask_message = (
                    f"Many users are asking about {top_theme} this week — I can book a slot for that!\n"
                    f"Here are the available appointment slots:\n{slot_list}\n"
                    "Which one works for you?"
                )
            else:
                ask_message = (
                    f"Here are the available appointment slots:\n{slot_list}\n"
                    "Which one works for you?"
                )
            return AgentResponse(message=ask_message, top_theme=top_theme, awaiting_response=True)

        elif parsed.intent == "RESCHEDULE":
            # Extract code from transcript (format KV-XXXX)
            match = re.search(r"KV-[A-Z0-9]{4}", transcript.upper())
            code_to_reschedule = None

            if match:
                code_to_reschedule = match.group(0)
            else:
                latest_b = self.persistence.get("latest_booking")
                if latest_b:
                    code_to_reschedule = latest_b.get("booking_code")

            if not code_to_reschedule:
                return AgentResponse(
                    message="I couldn't find a booking code in your request. Please specify your Booking Code (e.g. KV-XXXX) to reschedule."
                )

            old_booking_data = self.persistence.get(code_to_reschedule)
            if not old_booking_data:
                return AgentResponse(
                    message=f"No active booking found with code {code_to_reschedule}."
                )

            if old_booking_data.get("status") == "CANCELLED":
                return AgentResponse(
                    message=f"Booking {code_to_reschedule} is already cancelled."
                )

            old_slot = old_booking_data.get("date_time")

            if parsed.slot_preference:
                # Release the old slot and cancel the old booking, then book the new slot immediately
                self.slot_manager.release_slot(old_slot)
                old_booking_data["status"] = "CANCELLED"
                self.persistence.set(code_to_reschedule, old_booking_data)

                latest_b = self.persistence.get("latest_booking")
                if latest_b and latest_b.get("booking_code") == code_to_reschedule:
                    latest_b["status"] = "CANCELLED"
                    self.persistence.set("latest_booking", latest_b)

                try:
                    new_slot = self.slot_manager.resolve(parsed.slot_preference)
                    self.slot_manager.mark_booked(new_slot)
                except ValueError as e:
                    return AgentResponse(message=str(e))

                new_code = self._generate_booking_code()
                new_booking = Booking(
                    booking_code=new_code,
                    topic=old_booking_data.get("topic", "General Consultation"),
                    date_time=new_slot,
                    status="CONFIRMED",
                    top_theme=top_theme,
                    prep_notes=old_booking_data.get("prep_notes")
                )
                self.persistence.set(new_code, new_booking.model_dump())
                self.persistence.set("latest_booking", new_booking.model_dump())
                self._queue_mcp_followups(new_booking, top_theme)

                message = (
                    f"Your appointment has been rescheduled. Old booking {code_to_reschedule} is cancelled. "
                    f"Your new appointment is confirmed for {new_slot}. Your new Booking Code is {new_code}."
                )
                return AgentResponse(message=message, booking=new_booking, booking_code=new_code, top_theme=top_theme)

            # No slot preference given — ask the user to choose; leave the old booking untouched for now
            available = self.slot_manager.get_available_slots()
            if not available:
                return AgentResponse(message="No slots available to reschedule into.")

            self.persistence.set("pending_booking", {
                "type": "RESCHEDULE",
                "code_to_reschedule": code_to_reschedule,
                "old_slot": old_slot,
                "topic": old_booking_data.get("topic", "General Consultation"),
                "prep_notes": old_booking_data.get("prep_notes")
            })

            slot_list = self._slot_list_text(available)
            if top_theme:
                ask_message = (
                    f"Many users are asking about {top_theme} this week — happy to help reschedule for that!\n"
                    f"Here are the available appointment slots:\n{slot_list}\n"
                    "Which one would you like to move your appointment to?"
                )
            else:
                ask_message = (
                    f"Here are the available appointment slots:\n{slot_list}\n"
                    "Which one would you like to move your appointment to?"
                )
            return AgentResponse(message=ask_message, top_theme=top_theme, awaiting_response=True)

        elif parsed.intent == "PREPARE":
            # Find the booking topic to query RAG with
            topic_to_lookup = None
            if parsed.topic:
                topic_to_lookup = parsed.topic
            else:
                latest_b = self.persistence.get("latest_booking")
                if latest_b:
                    topic_to_lookup = latest_b.get("topic")

            rag_info = ""
            if topic_to_lookup:
                try:
                    rag = get_rag_engine()
                    answer = rag.answer_query(f"What should I prepare or know about {topic_to_lookup}?")
                    if answer and answer.text and "verified source for that" not in answer.text:
                        rag_info = f"\n\nHere is some information about {topic_to_lookup}:\n{answer.text}"
                except Exception:
                    pass

            prep_msg = "To prepare for your call, please have your investment goals and any existing portfolio statements ready."
            if rag_info:
                prep_msg += rag_info

            # Update the latest booking's prep notes if we have one
            latest_b_data = self.persistence.get("latest_booking")
            booking_obj = None
            if latest_b_data:
                latest_b_data["prep_notes"] = prep_msg
                self.persistence.set(latest_b_data["booking_code"], latest_b_data)
                self.persistence.set("latest_booking", latest_b_data)
                booking_obj = Booking(**latest_b_data)

            return AgentResponse(
                message=prep_msg,
                booking=booking_obj,
                booking_code=latest_b_data.get("booking_code") if latest_b_data else None,
                top_theme=top_theme
            )

        else:
            # intent is OTHER
            return AgentResponse(
                message="I can help you book, reschedule, or prepare for advisor appointments. For other questions, please consult our FAQ chatbot."
            )
