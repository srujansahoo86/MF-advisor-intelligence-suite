# Voice Booking: Queue Calendar Hold for Approval — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every confirmed voice booking or reschedule queues a "Calendar Hold Creator" action into the MCP approval queue, so it appears as a pending item in the dashboard's Approval Center.

**Architecture:** `BookingAgent` gains an `MCPOrchestrator` instance and a private `_queue_calendar_hold(booking)` helper, called from all 4 places where a `Booking` with `status="CONFIRMED"` is persisted as `latest_booking` (immediate BOOK, finalize BOOK, immediate RESCHEDULE, finalize RESCHEDULE).

**Tech Stack:** Python, pytest, `MCPOrchestrator` / `Persistence` (existing Phase 0 / Phase 4 modules), `langchain_groq` (existing, used by `IntentParser`/`SlotManager` — tests gated on `GROQ_API_KEY`).

**Spec:** `Docs/superpowers/specs/2026-06-12-booking-calendar-hold-approval-design.md`

---

### Task 1: Queue Calendar Hold Creator on booking confirmation

**Files:**
- Modify: `src/Phase3_Voice_Scheduler/booking_agent.py`
- Modify: `src/tests_integration/test_phase3.py`

**Background for the engineer:**

`BookingAgent` (`src/Phase3_Voice_Scheduler/booking_agent.py`) has 4 places where it builds a `Booking(... status="CONFIRMED")` and calls `self.persistence.set("latest_booking", booking.model_dump())`:

1. Immediate BOOK — inside `handle()`, in the `if parsed.intent == "BOOK"` branch, when `parsed.slot_preference` is truthy.
2. Finalize BOOK — inside `_finalize_pending_booking()`, the `# pending["type"] == "BOOK"` branch at the bottom of the method.
3. Immediate RESCHEDULE — inside `handle()`, in the `elif parsed.intent == "RESCHEDULE"` branch, when `parsed.slot_preference` is truthy.
4. Finalize RESCHEDULE — inside `_finalize_pending_booking()`, the `if pending["type"] == "RESCHEDULE":` branch.

Each of these 4 sites needs to also queue a `"Calendar Hold Creator"` action via `MCPOrchestrator.queue_action(...)` (`src/Phase4_MCP_Orchestration/orchestrator.py`), so the dashboard's Approval Center shows a pending item for the advisor to approve/reject. `MCPOrchestrator.__init__(self, db_path=None)` follows the same constructor pattern as `Persistence`/`SlotManager` (already used in `BookingAgent.__init__`).

`Persistence.get_pending_actions()` (`src/Phase0_Shared_Foundation/persistence.py:67`) returns `list[PendingAction]` for all actions currently in `PENDING` status — this is what tests will use to verify the queue.

This is TDD: write the failing test assertions first (Steps 1-3), confirm they fail (Step 4), then implement (Step 5), then confirm they pass (Step 6).

- [ ] **Step 1: Add Calendar Hold assertions to `test_booking_agent_full_flow`** (covers immediate BOOK + immediate RESCHEDULE — both confirm with a slot preference in the same message)

In `src/tests_integration/test_phase3.py`, find this block (it's right after the `latest_booking` checks, before the `# Process RESCHEDULE` comment):

```python
    latest_booking = persistence.get("latest_booking")
    assert latest_booking is not None
    assert latest_booking["booking_code"] == resp.booking_code

    # Process RESCHEDULE
```

Replace it with:

```python
    latest_booking = persistence.get("latest_booking")
    assert latest_booking is not None
    assert latest_booking["booking_code"] == resp.booking_code

    # A Calendar Hold Creator action was queued for approval
    pending_actions = persistence.get_pending_actions()
    book_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and resp.booking_code in a.payload.get("title", "")]
    assert len(book_holds) == 1
    assert book_holds[0].payload["start_time"] == resp.booking.date_time

    # Process RESCHEDULE
```

Then find the end of the same test (last 4 lines before the `# 9. Voice adapter boundaries...` comment):

```python
    # Verify slot availability
    sm = SlotManager(db_path=clean_db)
    assert sm.is_available(resp.booking.date_time) is True  # old slot should be released
    assert sm.is_available(resched_resp.booking.date_time) is False  # new slot should be booked

# 9. Voice adapter boundaries and grace fallbacks
```

Replace it with:

```python
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
```

- [ ] **Step 2: Add Calendar Hold assertions to `test_booking_agent_ask_then_book`** (covers finalize BOOK)

Find this block (right after `assert pending["type"] == "BOOK"`):

```python
    pending = persistence.get("pending_booking")
    assert pending is not None
    assert pending["type"] == "BOOK"

    # Reply with a slot choice
```

Replace it with:

```python
    pending = persistence.get("pending_booking")
    assert pending is not None
    assert pending["type"] == "BOOK"

    # No Calendar Hold Creator action queued yet — booking not confirmed
    assert persistence.get_pending_actions() == []

    # Reply with a slot choice
```

Then find the end of the same test (last 4 lines before the `# 12. RESCHEDULE with no slot preference...` comment):

```python
    # Pending state cleared, slot marked booked
    assert persistence.get("pending_booking") == {}
    sm = SlotManager(db_path=clean_db)
    assert sm.is_available(resp_book.booking.date_time) is False

# 12. RESCHEDULE with no slot preference asks first, then reschedules on reply (LLM-based)
```

Replace it with:

```python
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
```

- [ ] **Step 3: Add Calendar Hold assertions to `test_booking_agent_ask_then_reschedule`** (covers finalize RESCHEDULE)

Find this block (right after the initial booking's slot-availability check):

```python
    sm = SlotManager(db_path=clean_db)
    assert sm.is_available(old_slot) is False

    # Ask to reschedule without specifying a new date/time
```

Replace it with:

```python
    sm = SlotManager(db_path=clean_db)
    assert sm.is_available(old_slot) is False

    # A Calendar Hold Creator action was queued for the original booking
    pending_actions = persistence.get_pending_actions()
    old_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and old_code in a.payload.get("title", "")]
    assert len(old_holds) == 1
    assert old_holds[0].payload["start_time"] == old_slot

    # Ask to reschedule without specifying a new date/time
```

Then find this block (right after the pending-state checks):

```python
    pending = persistence.get("pending_booking")
    assert pending["type"] == "RESCHEDULE"
    assert pending["code_to_reschedule"] == old_code
    assert pending["old_slot"] == old_slot

    # Reply with a new slot choice
```

Replace it with:

```python
    pending = persistence.get("pending_booking")
    assert pending["type"] == "RESCHEDULE"
    assert pending["code_to_reschedule"] == old_code
    assert pending["old_slot"] == old_slot

    # No new Calendar Hold Creator action queued yet — reschedule not confirmed
    assert len(persistence.get_pending_actions()) == 1

    # Reply with a new slot choice
```

Then find the end of the file (last lines of the test):

```python
    # Old booking cancelled and slot released, new slot booked
    old_booking = persistence.get(old_code)
    assert old_booking["status"] == "CANCELLED"
    assert sm.is_available(old_slot) is True
    assert sm.is_available(resp_resched.booking.date_time) is False

    assert persistence.get("pending_booking") == {}
```

Replace it with:

```python
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
```

- [ ] **Step 4: Run the 3 modified tests to verify they FAIL**

Run: `pytest src/tests_integration/test_phase3.py::test_booking_agent_full_flow src/tests_integration/test_phase3.py::test_booking_agent_ask_then_book src/tests_integration/test_phase3.py::test_booking_agent_ask_then_reschedule -v`

Expected: All 3 FAIL with `AssertionError` on the new `len(...) == 1` / `len(...) == 0` checks (since `BookingAgent` never calls `queue_action`, `persistence.get_pending_actions()` always returns `[]`).

- [ ] **Step 5: Implement the `MCPOrchestrator` integration in `booking_agent.py`**

In `src/Phase3_Voice_Scheduler/booking_agent.py`:

**5a. Add the import.** Find:

```python
from .pii_deflector import PIIDeflector
from .intent_parser import IntentParser
from .slot_manager import SlotManager
```

Replace with:

```python
from .pii_deflector import PIIDeflector
from .intent_parser import IntentParser
from .slot_manager import SlotManager
from src.Phase4_MCP_Orchestration.orchestrator import MCPOrchestrator
```

**5b. Add the orchestrator to `__init__`.** Find:

```python
    def __init__(self, db_path: str = None):
        self.persistence = Persistence(db_path)
        self.pii_deflector = PIIDeflector()
        self.intent_parser = IntentParser()
        self.slot_manager = SlotManager(db_path)
```

Replace with:

```python
    def __init__(self, db_path: str = None):
        self.persistence = Persistence(db_path)
        self.pii_deflector = PIIDeflector()
        self.intent_parser = IntentParser()
        self.slot_manager = SlotManager(db_path)
        self.orchestrator = MCPOrchestrator(db_path)
```

**5c. Add the `_queue_calendar_hold` helper.** Find:

```python
    def _slot_list_text(self, available: list[str]) -> str:
        """Formats a list of available slots as a bulleted list."""
        return "\n".join(f"- {s}" for s in available)
```

Replace with:

```python
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
```

**5d. Call site — Finalize RESCHEDULE** (inside `_finalize_pending_booking`, `RESCHEDULE` branch). Find:

```python
            self.persistence.set(code, booking.model_dump())
            self.persistence.set("latest_booking", booking.model_dump())
            self.persistence.set("pending_booking", {})

            message = (
                f"Your appointment has been rescheduled. Old booking {old_code} is cancelled. "
```

Replace with:

```python
            self.persistence.set(code, booking.model_dump())
            self.persistence.set("latest_booking", booking.model_dump())
            self.persistence.set("pending_booking", {})
            self._queue_calendar_hold(booking)

            message = (
                f"Your appointment has been rescheduled. Old booking {old_code} is cancelled. "
```

**5e. Call site — Finalize BOOK** (inside `_finalize_pending_booking`, `BOOK` branch). Find:

```python
        self.persistence.set(code, booking.model_dump())
        self.persistence.set("latest_booking", booking.model_dump())
        self.persistence.set("pending_booking", {})

        message = self._book_confirmation_message(new_slot, code, top_theme)
```

Replace with:

```python
        self.persistence.set(code, booking.model_dump())
        self.persistence.set("latest_booking", booking.model_dump())
        self.persistence.set("pending_booking", {})
        self._queue_calendar_hold(booking)

        message = self._book_confirmation_message(new_slot, code, top_theme)
```

**5f. Call site — Immediate BOOK** (inside `handle()`, `BOOK` branch with `slot_preference`). Find:

```python
                self.persistence.set(code, booking.model_dump())
                self.persistence.set("latest_booking", booking.model_dump())

                message = self._book_confirmation_message(slot, code, top_theme)
```

Replace with:

```python
                self.persistence.set(code, booking.model_dump())
                self.persistence.set("latest_booking", booking.model_dump())
                self._queue_calendar_hold(booking)

                message = self._book_confirmation_message(slot, code, top_theme)
```

**5g. Call site — Immediate RESCHEDULE** (inside `handle()`, `RESCHEDULE` branch with `slot_preference`). Find:

```python
                self.persistence.set(new_code, new_booking.model_dump())
                self.persistence.set("latest_booking", new_booking.model_dump())

                message = (
                    f"Your appointment has been rescheduled. Old booking {code_to_reschedule} is cancelled. "
```

Replace with:

```python
                self.persistence.set(new_code, new_booking.model_dump())
                self.persistence.set("latest_booking", new_booking.model_dump())
                self._queue_calendar_hold(new_booking)

                message = (
                    f"Your appointment has been rescheduled. Old booking {code_to_reschedule} is cancelled. "
```

- [ ] **Step 6: Run the 3 modified tests to verify they PASS**

Run: `pytest src/tests_integration/test_phase3.py::test_booking_agent_full_flow src/tests_integration/test_phase3.py::test_booking_agent_ask_then_book src/tests_integration/test_phase3.py::test_booking_agent_ask_then_reschedule -v`

Expected: `3 passed`

- [ ] **Step 7: Run the full Phase 3 suite (regression check)**

Run: `pytest src/tests_integration/test_phase3.py -v`

Expected: `13 passed` (all tests, no regressions to `test_slot_manager_returns_valid_slot`, `test_prepare_intent_rag_lookup`, etc.)

- [ ] **Step 8: Manual verification checkpoint**

This project is not a git repository, so there is no commit step. Instead:

1. Restart the local server so it picks up the change:
   - Find and kill the existing `uvicorn src.api.main:app` process (Windows: `netstat -ano | findstr :8000` then `taskkill //PID <pid> //F`)
   - Start it again: `python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000`
2. Verify via curl:
   - `curl -X POST http://127.0.0.1:8000/api/voice -H "Content-Type: application/json" -d "{\"transcript\": \"Book a call about exit load on Monday morning\"}"` → should return a `CONFIRMED` booking
   - `curl http://127.0.0.1:8000/api/actions/pending` → should now return a list containing one `"Calendar Hold Creator"` action with `"status": "PENDING"`, `payload.title` containing the booking code from the previous response, and `payload.start_time` equal to the booked slot.
