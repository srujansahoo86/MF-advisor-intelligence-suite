import os
import re
import pytest
from src.Phase3_Voice_Scheduler.pii_deflector import PIIDeflector
from src.Phase3_Voice_Scheduler.intent_parser import IntentParser
from src.Phase3_Voice_Scheduler.slot_manager import SlotManager
from src.Phase3_Voice_Scheduler.booking_agent import BookingAgent
from src.Phase3_Voice_Scheduler.voice_adapter import VoiceAdapter
from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.persistence import Persistence
from src.Phase0_Shared_Foundation.schemas import Booking
from unittest.mock import patch
from src.Phase3_Voice_Scheduler.intent_parser import ParsedIntent
from src.Phase3_Voice_Scheduler.booking_agent import (
    _transcript_mentions_time,
    _is_goodbye,
)

TEST_DB_PATH = "./data/test_phase3.db"

@pytest.fixture
def clean_db():
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    yield TEST_DB_PATH
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

has_groq_key = bool(os.getenv("GROQ_API_KEY"))
skip_no_groq = pytest.mark.skipif(not has_groq_key, reason="GROQ_API_KEY environment variable not set")

# 1. PII deflector triggers on phone
def test_pii_deflector_triggers_on_phone():
    deflector = PIIDeflector()
    has_pii, message = deflector.check("Hi, my phone is 9876543210. Please call me.")
    assert has_pii is True
    assert "don't share personal details" in message
    assert Config.ADVISOR_SECURE_LINK in message

# 2. PII deflector passes clean
def test_pii_deflector_passes_clean():
    deflector = PIIDeflector()
    has_pii, message = deflector.check("I want to book an appointment for Monday morning.")
    assert has_pii is False
    assert message == ""

# 3. Booking code format
def test_booking_code_format(clean_db):
    agent = BookingAgent(db_path=clean_db)
    code = agent._generate_booking_code()
    assert re.match(r"^KV-[A-Z0-9]{4}$", code) is not None

# 4. Slot manager returns valid slot
def test_slot_manager_returns_valid_slot(clean_db):
    sm = SlotManager(db_path=clean_db)
    res = sm.resolve(None)
    assert res in Config.AVAILABLE_SLOTS

# 14. Time-word detector used to guard against hallucinated slot_preference
def test_transcript_mentions_time_detects_day_and_time_words():
    assert _transcript_mentions_time("book a call for Monday morning") is True
    assert _transcript_mentions_time("can we do this at 3pm") is True
    assert _transcript_mentions_time("can we do this at 3 PM") is True
    assert _transcript_mentions_time("I want to book my appointment") is False
    assert _transcript_mentions_time("") is False

# 15. handle() discards a hallucinated slot_preference when the transcript
# has no day/time words, falling back to the ask-for-options flow
def test_handle_discards_hallucinated_slot_preference(clean_db):
    agent = BookingAgent(db_path=clean_db)

    with patch.object(
        agent.intent_parser,
        "parse",
        return_value=ParsedIntent(
            intent="BOOK",
            topic="General Consultation",
            slot_preference="Monday 10:00 AM",
        ),
    ):
        resp = agent.handle("I want to book my appointment")

    assert resp.booking is None
    assert resp.booking_code is None
    assert resp.awaiting_response is True
    assert any(slot in resp.message for slot in Config.AVAILABLE_SLOTS)

    pending = Persistence(clean_db).get("pending_booking")
    assert pending["type"] == "BOOK"

# 5. Intent parser BOOK (LLM-based)
@skip_no_groq
def test_intent_parser_book():
    parser = IntentParser()
    parsed = parser.parse("I want to book a call about my SIP mandate.")
    assert parsed.intent == "BOOK"
    assert parsed.topic is not None
    assert "SIP" in parsed.topic or "mandate" in parsed.topic.lower()

# 6. Intent parser RESCHEDULE (LLM-based)
@skip_no_groq
def test_intent_parser_reschedule():
    parser = IntentParser()
    parsed = parser.parse("Can I reschedule my appointment to Friday afternoon?")
    assert parsed.intent == "RESCHEDULE"
    assert parsed.slot_preference is not None
    assert "Friday" in parsed.slot_preference or "afternoon" in parsed.slot_preference.lower()

# 7. Intent parser PREPARE (LLM-based)
@skip_no_groq
def test_intent_parser_prepare():
    parser = IntentParser()
    parsed = parser.parse("What should I prepare for my call?")
    assert parsed.intent == "PREPARE"

# 8. Booking agent full flow (LLM-based)
@skip_no_groq
def test_booking_agent_full_flow(clean_db):
    persistence = Persistence(clean_db)
    
    # Seed a mock latest_pulse to verify top theme greeting
    mock_pulse = {
        "top_themes": [{"theme_name": "Direct Plan Switch", "description": "Switching from regular to direct."}],
        "user_quotes": ["how do i switch regular to direct"],
        "key_observation": "Users want to switch plans.",
        "action_ideas": ["Show button", "Add guide", "Explain fees"],
        "word_count": 50
    }
    persistence.set("latest_pulse", mock_pulse)
    
    # Process BOOK
    adapter = VoiceAdapter(db_path=clean_db)
    resp = adapter.process("I want to book a call about exit load confusion on Monday morning")
    
    assert resp.booking is not None
    assert resp.booking_code is not None
    assert re.match(r"^KV-[A-Z0-9]{4}$", resp.booking_code) is not None
    assert resp.booking.booking_code == resp.booking_code
    assert resp.booking.status == "CONFIRMED"
    assert any(day in resp.booking.date_time for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    assert resp.top_theme == "Direct Plan Switch"
    assert "Direct Plan Switch" in resp.message
    
    # Verify persistence
    saved_booking = persistence.get(resp.booking_code)
    assert saved_booking is not None
    assert saved_booking["booking_code"] == resp.booking_code
    
    latest_booking = persistence.get("latest_booking")
    assert latest_booking is not None
    assert latest_booking["booking_code"] == resp.booking_code

    # A Calendar Hold Creator action was queued for approval
    pending_actions = persistence.get_pending_actions()
    book_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and resp.booking_code in a.payload.get("title", "")]
    assert len(book_holds) == 1
    assert book_holds[0].payload["start_time"] == resp.booking.date_time

    # Process RESCHEDULE
    resched_resp = adapter.process(f"Can I reschedule {resp.booking_code} to Friday afternoon?")
    assert resched_resp.booking is not None
    assert resched_resp.booking_code != resp.booking_code  # should generate a new code
    assert resched_resp.booking.status == "CONFIRMED"
    assert any(day in resched_resp.booking.date_time for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    
    # Verify old code is cancelled and slot is released
    old_booking = persistence.get(resp.booking_code)
    assert old_booking["status"] == "CANCELLED"
    
    # Verify slot availability
    sm = SlotManager(db_path=clean_db)
    assert sm.is_available(resp.booking.date_time) is True  # old slot should be released
    assert sm.is_available(resched_resp.booking.date_time) is False  # new slot should be booked

    # A second Calendar Hold Creator action was queued for the rescheduled booking
    pending_actions = persistence.get_pending_actions()
    resched_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and resched_resp.booking_code in a.payload.get("title", "")]
    assert len(resched_holds) == 1
    assert resched_holds[0].payload["start_time"] == resched_resp.booking.date_time
    assert len(pending_actions) == 2

# 9. Voice adapter boundaries and grace fallbacks
def test_voice_adapter_empty():
    adapter = VoiceAdapter(db_path=TEST_DB_PATH)
    resp = adapter.process("")
    assert "I couldn't hear you clearly" in resp.message
    assert resp.booking is None

def test_voice_adapter_too_long():
    adapter = VoiceAdapter(db_path=TEST_DB_PATH)
    long_input = "a " * 300  # 600 chars
    # Should run agent and not raise errors
    resp = adapter.process(long_input)
    assert resp is not None

# 10. PREPARE intent with RAG lookup (LLM-based)
@skip_no_groq
def test_prepare_intent_rag_lookup(clean_db):
    persistence = Persistence(clean_db)
    # Book a call first
    adapter = VoiceAdapter(db_path=clean_db)
    resp_book = adapter.process("Book a call about HDFC fund fees on Monday morning")
    assert resp_book.booking is not None

    # Now ask to prepare
    resp_prep = adapter.process("What should I prepare for my call?")
    assert "prepare" in resp_prep.message.lower() or "investment" in resp_prep.message.lower()
    
    # Retrieve latest booking and verify prep notes
    latest_b = persistence.get("latest_booking")
    assert latest_b["prep_notes"] is not None

# 11. BOOK with no slot preference asks first, then books on reply (LLM-based)
@skip_no_groq
def test_booking_agent_ask_then_book(clean_db):
    persistence = Persistence(clean_db)
    adapter = VoiceAdapter(db_path=clean_db)

    # Ask to book without specifying a date/time
    resp_ask = adapter.process("I want to book my appointment")
    assert resp_ask.booking is None
    assert resp_ask.booking_code is None
    assert any(slot in resp_ask.message for slot in Config.AVAILABLE_SLOTS)

    pending = persistence.get("pending_booking")
    assert pending is not None
    assert pending["type"] == "BOOK"

    # No Calendar Hold Creator action queued yet — booking not confirmed
    assert persistence.get_pending_actions() == []

    # Reply with a slot choice
    resp_book = adapter.process("Monday 10:00 AM")
    assert resp_book.booking is not None
    assert resp_book.booking.status == "CONFIRMED"
    assert resp_book.booking.date_time in Config.AVAILABLE_SLOTS

    # Pending state cleared, slot marked booked
    assert persistence.get("pending_booking") == {}
    sm = SlotManager(db_path=clean_db)
    assert sm.is_available(resp_book.booking.date_time) is False

    # A Calendar Hold Creator action was queued once the booking was confirmed
    pending_actions = persistence.get_pending_actions()
    book_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and resp_book.booking_code in a.payload.get("title", "")]
    assert len(book_holds) == 1
    assert book_holds[0].payload["start_time"] == resp_book.booking.date_time

# 12. RESCHEDULE with no slot preference asks first, then reschedules on reply (LLM-based)
@skip_no_groq
def test_booking_agent_ask_then_reschedule(clean_db):
    persistence = Persistence(clean_db)
    adapter = VoiceAdapter(db_path=clean_db)

    # Book a slot first (slot specified, books immediately)
    resp_book = adapter.process("Book a call about exit load on Monday morning")
    assert resp_book.booking is not None
    old_code = resp_book.booking_code
    old_slot = resp_book.booking.date_time

    sm = SlotManager(db_path=clean_db)
    assert sm.is_available(old_slot) is False

    # A Calendar Hold Creator action was queued for the original booking
    pending_actions = persistence.get_pending_actions()
    old_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and old_code in a.payload.get("title", "")]
    assert len(old_holds) == 1
    assert old_holds[0].payload["start_time"] == old_slot

    # Ask to reschedule without specifying a new date/time
    resp_ask = adapter.process(f"Can I reschedule {old_code}?")
    assert resp_ask.booking is None
    assert any(slot in resp_ask.message for slot in Config.AVAILABLE_SLOTS)

    # Old booking is untouched while waiting for the user's choice
    old_booking = persistence.get(old_code)
    assert old_booking["status"] == "CONFIRMED"
    assert sm.is_available(old_slot) is False

    pending = persistence.get("pending_booking")
    assert pending["type"] == "RESCHEDULE"
    assert pending["code_to_reschedule"] == old_code
    assert pending["old_slot"] == old_slot

    # No new Calendar Hold Creator action queued yet — reschedule not confirmed
    assert len(persistence.get_pending_actions()) == 1

    # Reply with a new slot choice
    resp_resched = adapter.process("Friday afternoon")
    assert resp_resched.booking is not None
    new_code = resp_resched.booking_code
    assert new_code != old_code
    assert resp_resched.booking.status == "CONFIRMED"

    # Old booking cancelled and slot released, new slot booked
    old_booking = persistence.get(old_code)
    assert old_booking["status"] == "CANCELLED"
    assert sm.is_available(old_slot) is True
    assert sm.is_available(resp_resched.booking.date_time) is False

    assert persistence.get("pending_booking") == {}

    # A second Calendar Hold Creator action was queued for the rescheduled booking
    pending_actions = persistence.get_pending_actions()
    new_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and new_code in a.payload.get("title", "")]
    assert len(new_holds) == 1
    assert new_holds[0].payload["start_time"] == resp_resched.booking.date_time
    assert len(pending_actions) == 2

# 13. While awaiting a slot choice, an unrelated/unmatched reply (e.g. noise,
# silence, or an echo of the assistant's own prompt) must NOT silently book a
# slot — it should re-ask and keep listening (LLM-based)
@skip_no_groq
def test_booking_agent_reasks_on_unmatched_slot_reply(clean_db):
    persistence = Persistence(clean_db)
    adapter = VoiceAdapter(db_path=clean_db)

    # Ask to book without specifying a date/time
    resp_ask = adapter.process("I want to book my appointment")
    assert resp_ask.booking is None
    assert resp_ask.awaiting_response is True

    # Reply that does not select any of the offered slots
    resp_noise = adapter.process("Many users are asking about fees this week, here are the available slots")
    assert resp_noise.booking is None
    assert resp_noise.booking_code is None
    assert resp_noise.awaiting_response is True
    assert any(slot in resp_noise.message for slot in Config.AVAILABLE_SLOTS)

    # Pending booking must remain open so the mic stays on
    pending = persistence.get("pending_booking")
    assert pending is not None
    assert pending["type"] == "BOOK"

    # No booking should have been queued for approval yet
    assert persistence.get_pending_actions() == []

    # A real slot choice now completes the booking
    resp_book = adapter.process("Monday 10:00 AM")
    assert resp_book.booking is not None
    assert resp_book.booking.status == "CONFIRMED"
    assert resp_book.booking.date_time in Config.AVAILABLE_SLOTS
    assert persistence.get("pending_booking") == {}

# 16. A goodbye phrase ends the session immediately (no LLM needed)
def test_goodbye_ends_session(clean_db):
    adapter = VoiceAdapter(db_path=clean_db)
    resp = adapter.process("Thanks, that's all, bye")

    assert resp.session_ended is True
    assert resp.message != ""
    assert resp.booking is None

    assert Persistence(clean_db).get("pending_booking") == {}

# 16b. A goodbye phrase clears a populated pending_booking without needing the LLM
def test_goodbye_clears_pending_booking(clean_db):
    persistence = Persistence(clean_db)
    persistence.set("pending_booking", {"type": "BOOK", "topic": "General Consultation"})

    adapter = VoiceAdapter(db_path=clean_db)
    resp = adapter.process("Thanks, that's all, bye")

    assert resp.session_ended is True
    assert resp.booking is None
    assert persistence.get("pending_booking") == {}

# 17. Saying goodbye while a slot choice is pending clears the pending
# booking and ends the session without creating a booking (LLM-based)
@skip_no_groq
def test_goodbye_mid_pending_booking(clean_db):
    persistence = Persistence(clean_db)
    adapter = VoiceAdapter(db_path=clean_db)

    resp_ask = adapter.process("I want to book my appointment")
    assert persistence.get("pending_booking")["type"] == "BOOK"

    resp_bye = adapter.process("Never mind, that's all, bye")
    assert resp_bye.session_ended is True
    assert resp_bye.booking is None
    assert persistence.get("pending_booking") == {}


# 18. Booking and releasing a slot still works with the new storage shape
def test_slot_manager_rolling_availability(clean_db):
    sm = SlotManager(db_path=clean_db)
    slot = "Monday 10:00 AM"

    assert sm.is_available(slot) is True
    sm.mark_booked(slot)
    assert sm.is_available(slot) is False
    assert slot not in sm.get_available_slots()

    sm.release_slot(slot)
    assert sm.is_available(slot) is True
    assert slot in sm.get_available_slots()


# 19. A booking whose occurrence date is in the past is pruned, freeing the
# slot label for its next upcoming occurrence
def test_slot_manager_prunes_expired_bookings(clean_db):
    sm = SlotManager(db_path=clean_db)
    persistence = Persistence(clean_db)
    slot = "Tuesday 3:00 PM"

    persistence.set("booked_slots", [{"slot": slot, "date": "2000-01-01"}])

    assert sm.is_available(slot) is True
    assert slot in sm.get_available_slots()
    assert persistence.get("booked_slots") == []


# 20. Legacy booked_slots (flat list of label strings) is treated as empty
def test_slot_manager_ignores_legacy_string_entries(clean_db):
    sm = SlotManager(db_path=clean_db)
    persistence = Persistence(clean_db)

    persistence.set("booked_slots", ["Monday 10:00 AM", "Friday 3:00 PM"])

    assert sm.get_booked_slots() == []
    assert persistence.get("booked_slots") == []
    assert sm.get_available_slots() == Config.AVAILABLE_SLOTS


# 21. _queue_doc_append appends a dated markdown entry referencing the booking
def test_queue_doc_append_writes_shared_notes_entry(clean_db):
    persistence = Persistence(clean_db)
    persistence.set("latest_pulse", {
        "top_themes": [{"theme_name": "Exit Load Confusion", "description": "Users confused about exit loads."}],
        "user_quotes": ["What is the exit load?"],
        "key_observation": "Many users confused about exit loads.",
        "action_ideas": ["a", "b", "c"],
        "word_count": 10,
    })
    persistence.set("latest_fee_explainer", {
        "bullets": ["b1", "b2", "b3", "b4", "b5", "b6"],
        "source_links": ["https://www.amfiindia.com/x", "https://www.sebi.gov.in/y"],
        "last_checked": "Last checked: 2026-06-10",
    })

    agent = BookingAgent(db_path=clean_db)
    booking = Booking(
        booking_code="KV-TEST",
        topic="Exit load query",
        date_time="Monday 10:00 AM",
        status="CONFIRMED",
    )

    agent._queue_doc_append(booking, "Exit Load Confusion")

    pending_actions = persistence.get_pending_actions()
    doc_actions = [a for a in pending_actions if a.tool_name == "Doc Append"]
    assert len(doc_actions) == 1

    payload = doc_actions[0].payload
    assert payload["file_path"] == Config.SHARED_NOTES_PATH
    assert "KV-TEST" in payload["content"]
    assert "Exit Load Confusion" in payload["content"]
    assert "Many users confused about exit loads." in payload["content"]
    assert "Last checked: 2026-06-10" in payload["content"]


# 22. _queue_email_draft queues an Email Draft Generator action for the advisor
def test_queue_email_draft_for_booking(clean_db):
    persistence = Persistence(clean_db)
    agent = BookingAgent(db_path=clean_db)
    booking = Booking(
        booking_code="KV-TEST",
        topic="Exit load query",
        date_time="Monday 10:00 AM",
        status="CONFIRMED",
    )

    agent._queue_email_draft(booking)

    pending_actions = persistence.get_pending_actions()
    email_actions = [a for a in pending_actions if a.tool_name == "Email Draft Generator"]
    assert len(email_actions) == 1

    payload = email_actions[0].payload
    assert payload["recipient"] == "advisor@kuvera.in"
    assert "KV-TEST" in payload["subject"]
    assert "Exit load query" in payload["subject"]
    assert payload["topic"] == "Exit load query"


# 23. _queue_mcp_followups queues Calendar Hold, Doc Append, and Email Draft Generator
def test_queue_mcp_followups_queues_all_three_actions(clean_db):
    persistence = Persistence(clean_db)
    agent = BookingAgent(db_path=clean_db)
    booking = Booking(
        booking_code="KV-TEST",
        topic="Exit load query",
        date_time="Monday 10:00 AM",
        status="CONFIRMED",
    )

    agent._queue_mcp_followups(booking, "Exit Load Confusion")

    pending_actions = persistence.get_pending_actions()
    tool_names = {a.tool_name for a in pending_actions}
    assert tool_names == {"Calendar Hold Creator", "Doc Append", "Email Draft Generator"}
    assert len(pending_actions) == 3
