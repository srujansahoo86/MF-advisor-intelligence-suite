# Voice Scheduler: Ask Before Booking/Rescheduling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the voice agent receives a BOOK or RESCHEDULE request with no date/time, it lists available slots and asks the user to choose, then books/reschedules on the user's reply (instead of silently auto-picking the first open slot).

**Architecture:** Add a `pending_booking` record to the existing SQLite key-value store (`Persistence`, same mechanism as `latest_booking`). `BookingAgent.handle()` checks for this record first; if present, the incoming transcript is treated as the user's slot choice and finalized via a new `_finalize_pending_booking()` helper. If absent, BOOK/RESCHEDULE behave as today when a slot preference is given, or set `pending_booking` and ask when it isn't.

**Tech Stack:** Python, pytest, existing `Persistence`/`SlotManager`/`IntentParser`/`Booking` classes — no new dependencies.

**Note:** This project is not a git repository, so steps that would normally end with `git commit` are replaced with a manual verification checkpoint instead.

---

### Task 1: Ask-before-booking/rescheduling in `BookingAgent`

**Files:**
- Modify: `src/Phase3_Voice_Scheduler/booking_agent.py:50-227` (the entire `handle` method, plus new helper methods added alongside it)
- Test: `src/tests_integration/test_phase3.py` (append two new tests after the existing `test_prepare_intent_rag_lookup`, i.e. after line 166)

- [ ] **Step 1: Write failing test for the BOOK ask-then-book flow**

Append to `src/tests_integration/test_phase3.py`:

```python
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

    # Reply with a slot choice
    resp_book = adapter.process("Monday 10:00 AM")
    assert resp_book.booking is not None
    assert resp_book.booking.status == "CONFIRMED"
    assert resp_book.booking.date_time in Config.AVAILABLE_SLOTS

    # Pending state cleared, slot marked booked
    assert persistence.get("pending_booking") == {}
    sm = SlotManager(db_path=clean_db)
    assert sm.is_available(resp_book.booking.date_time) is False
```

- [ ] **Step 2: Write failing test for the RESCHEDULE ask-then-reschedule flow**

Append to `src/tests_integration/test_phase3.py`, directly after the test from Step 1:

```python
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
```

- [ ] **Step 3: Run the new tests and verify they fail**

Run: `python -m pytest "src/tests_integration/test_phase3.py::test_booking_agent_ask_then_book" "src/tests_integration/test_phase3.py::test_booking_agent_ask_then_reschedule" -v`

Expected: Both `FAIL`.
- `test_booking_agent_ask_then_book` fails on `assert resp_ask.booking is None` because today's code books immediately.
- `test_booking_agent_ask_then_reschedule` fails on `assert resp_ask.booking is None` for the same reason.

- [ ] **Step 4: Replace `BookingAgent.handle()` and add helper methods**

In `src/Phase3_Voice_Scheduler/booking_agent.py`, replace everything from line 50 (`def handle(self, transcript: str) -> AgentResponse:`) to the end of the file (line 227) with:

```python
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

    def _finalize_pending_booking(self, pending: dict, transcript: str, top_theme: Optional[str]) -> AgentResponse:
        """Resolves the user's slot choice and completes a pending BOOK or RESCHEDULE."""
        try:
            new_slot = self.slot_manager.resolve(transcript)
            self.slot_manager.mark_booked(new_slot)
        except ValueError as e:
            return AgentResponse(message=str(e))

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

        # 2. Retrieve top theme (if available)
        top_theme = self._get_top_theme()

        # 3. If a booking/reschedule is awaiting a slot choice, this transcript is the answer
        pending = self.persistence.get("pending_booking")
        if pending:
            return self._finalize_pending_booking(pending, transcript, top_theme)

        # 4. Parse Intent
        parsed = self.intent_parser.parse(transcript)

        # 5. Handle Intents
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
            return AgentResponse(message=ask_message, top_theme=top_theme)

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
            ask_message = (
                f"Here are the available appointment slots:\n{slot_list}\n"
                "Which one would you like to move your appointment to?"
            )
            return AgentResponse(message=ask_message, top_theme=top_theme)

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
                    rag = RAGEngine()
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
```

- [ ] **Step 5: Run the new tests and verify they pass**

Run: `python -m pytest "src/tests_integration/test_phase3.py::test_booking_agent_ask_then_book" "src/tests_integration/test_phase3.py::test_booking_agent_ask_then_reschedule" -v`

Expected: Both `PASS`.

- [ ] **Step 6: Run the full Phase 3 suite to check for regressions**

Run: `python -m pytest src/tests_integration/test_phase3.py -v`

Expected: All tests `PASS` (12 total — the 10 existing plus the 2 new ones). In particular:
- `test_slot_manager_returns_valid_slot` still passes (unchanged `SlotManager.resolve` behavior).
- `test_booking_agent_full_flow` still passes (slot preference present in both BOOK and RESCHEDULE messages, so both take the immediate path).

If anything fails, do not proceed — re-open Phase 1 of systematic-debugging on the failing test before touching code further.

---

### Manual verification checkpoint (replaces commit)

- [ ] Confirm Step 6 passed with all tests green.
- [ ] Spot-check `src/Phase3_Voice_Scheduler/booking_agent.py` — `handle()` should be ~120 lines shorter in net new logic but the PREPARE/OTHER branches must be byte-for-byte identical to the original (no accidental edits).
