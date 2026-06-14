# Voice Scheduler MCP Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a voice booking/reschedule is confirmed, queue `Doc Append` and `Email Draft Generator` MCP actions (in addition to the existing `Calendar Hold Creator`) so all three required MCP tools are demonstrated through the live Approval Centre.

**Architecture:** Three new `BookingAgent` helper methods (`_queue_doc_append`, `_queue_email_draft`, `_queue_mcp_followups`) follow the existing `_queue_calendar_hold` pattern. `_queue_mcp_followups` wraps all three and replaces the 4 existing `_queue_calendar_hold` call sites.

**Tech Stack:** Python, pytest, SQLite-backed `Persistence`, `MCPOrchestrator`.

**Reference spec:** `Docs/superpowers/specs/2026-06-14-voice-scheduler-mcp-followups-design.md`

---

### Task 1: `Config.SHARED_NOTES_PATH` + `_queue_doc_append`

**Files:**
- Modify: `src/Phase0_Shared_Foundation/config.py`
- Modify: `src/Phase3_Voice_Scheduler/booking_agent.py`
- Test: `src/tests_integration/test_phase3.py`

- [ ] **Step 1: Write the failing test**

Add to `src/tests_integration/test_phase3.py`. First add this import near the top, alongside the existing `Booking`-less imports (the file currently does not import `Booking` — add it next to the `Config`/`Persistence` imports):

```python
from src.Phase0_Shared_Foundation.schemas import Booking
```

Then append this test at the end of the file:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_queue_doc_append_writes_shared_notes_entry -v`
Expected: FAIL with `AttributeError: 'Config' object has no attribute 'SHARED_NOTES_PATH'` or `AttributeError: 'BookingAgent' object has no attribute '_queue_doc_append'`

- [ ] **Step 3: Add `SHARED_NOTES_PATH` to Config**

In `src/Phase0_Shared_Foundation/config.py`, add this line inside the `Phase 3 — Voice Scheduler` section (near `ADVISOR_SECURE_LINK`):

```python
    SHARED_NOTES_PATH = os.getenv("SHARED_NOTES_PATH", "./data/shared_notes.md")
```

- [ ] **Step 4: Add imports and `_queue_doc_append` to `booking_agent.py`**

At the top of `src/Phase3_Voice_Scheduler/booking_agent.py`, change:

```python
import re
import random
import string
from dataclasses import dataclass
from typing import Optional
```

to:

```python
import re
import random
import string
from dataclasses import dataclass
from datetime import date
from typing import Optional
```

And change:

```python
from src.Phase0_Shared_Foundation.persistence import Persistence
from src.Phase0_Shared_Foundation.schemas import Booking
from src.Phase1_FAQ_Chatbot.rag_engine import get_rag_engine
```

to:

```python
from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.persistence import Persistence
from src.Phase0_Shared_Foundation.schemas import Booking
from src.Phase1_FAQ_Chatbot.rag_engine import get_rag_engine
```

Then add this new method directly after `_queue_calendar_hold`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_queue_doc_append_writes_shared_notes_entry -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/Phase0_Shared_Foundation/config.py src/Phase3_Voice_Scheduler/booking_agent.py src/tests_integration/test_phase3.py
git commit -m "feat: queue Doc Append action with booking details on confirmation"
```

---

### Task 2: `_queue_email_draft`

**Files:**
- Modify: `src/Phase3_Voice_Scheduler/booking_agent.py`
- Test: `src/tests_integration/test_phase3.py`

- [ ] **Step 1: Write the failing test**

Append to `src/tests_integration/test_phase3.py`:

```python
# 22. _queue_email_draft queues an Email Draft Generator action referencing the booking
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
    assert payload["topic"] == "Exit load query"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_queue_email_draft_for_booking -v`
Expected: FAIL with `AttributeError: 'BookingAgent' object has no attribute '_queue_email_draft'`

- [ ] **Step 3: Implement `_queue_email_draft`**

In `src/Phase3_Voice_Scheduler/booking_agent.py`, add this new method directly after `_queue_doc_append`:

```python
    def _queue_email_draft(self, booking: Booking) -> None:
        """Queues an Email Draft Generator action for advisor approval."""
        self.orchestrator.queue_action("Email Draft Generator", {
            "recipient": "advisor@kuvera.in",
            "subject": f"Pre-meeting brief: {booking.topic} ({booking.booking_code})",
            "topic": booking.topic,
        })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_queue_email_draft_for_booking -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/Phase3_Voice_Scheduler/booking_agent.py src/tests_integration/test_phase3.py
git commit -m "feat: queue Email Draft Generator action on booking confirmation"
```

---

### Task 3: `_queue_mcp_followups`

**Files:**
- Modify: `src/Phase3_Voice_Scheduler/booking_agent.py`
- Test: `src/tests_integration/test_phase3.py`

- [ ] **Step 1: Write the failing test**

Append to `src/tests_integration/test_phase3.py`:

```python
# 23. _queue_mcp_followups queues Calendar Hold, Doc Append, and Email Draft together
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_queue_mcp_followups_queues_all_three_actions -v`
Expected: FAIL with `AttributeError: 'BookingAgent' object has no attribute '_queue_mcp_followups'`

- [ ] **Step 3: Implement `_queue_mcp_followups`**

In `src/Phase3_Voice_Scheduler/booking_agent.py`, add this new method directly after `_queue_email_draft`:

```python
    def _queue_mcp_followups(self, booking: Booking, top_theme: Optional[str]) -> None:
        """Queues all required MCP actions for a confirmed booking/reschedule."""
        self._queue_calendar_hold(booking)
        self._queue_doc_append(booking, top_theme)
        self._queue_email_draft(booking)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_queue_mcp_followups_queues_all_three_actions -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/Phase3_Voice_Scheduler/booking_agent.py src/tests_integration/test_phase3.py
git commit -m "feat: add _queue_mcp_followups combining all three MCP actions"
```

---

### Task 4: Wire `_queue_mcp_followups` into all 4 confirmation paths

**Files:**
- Modify: `src/Phase3_Voice_Scheduler/booking_agent.py`
- Test: `src/tests_integration/test_phase3.py`

This task extends the 3 existing Groq-gated integration tests with assertions
for `Doc Append` and `Email Draft Generator`, confirms they fail against the
current production code, then wires up `_queue_mcp_followups` so they pass.

- [ ] **Step 1: Extend `test_booking_agent_full_flow`**

In `src/tests_integration/test_phase3.py`, find this block (the BOOK confirmation check):

```python
    # A Calendar Hold Creator action was queued for approval
    pending_actions = persistence.get_pending_actions()
    book_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and resp.booking_code in a.payload.get("title", "")]
    assert len(book_holds) == 1
    assert book_holds[0].payload["start_time"] == resp.booking.date_time
```

Replace it with:

```python
    # A Calendar Hold Creator action was queued for approval
    pending_actions = persistence.get_pending_actions()
    book_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and resp.booking_code in a.payload.get("title", "")]
    assert len(book_holds) == 1
    assert book_holds[0].payload["start_time"] == resp.booking.date_time

    # A Doc Append action was queued referencing the booking code
    book_docs = [a for a in pending_actions if a.tool_name == "Doc Append" and resp.booking_code in a.payload.get("content", "")]
    assert len(book_docs) == 1
    assert book_docs[0].payload["file_path"] == Config.SHARED_NOTES_PATH

    # An Email Draft Generator action was queued referencing the booking code
    book_emails = [a for a in pending_actions if a.tool_name == "Email Draft Generator" and resp.booking_code in a.payload.get("subject", "")]
    assert len(book_emails) == 1
    assert book_emails[0].payload["recipient"] == "advisor@kuvera.in"
```

Then find this block (the RESCHEDULE confirmation check, at the end of the same test):

```python
    # A second Calendar Hold Creator action was queued for the rescheduled booking
    pending_actions = persistence.get_pending_actions()
    resched_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and resched_resp.booking_code in a.payload.get("title", "")]
    assert len(resched_holds) == 1
    assert resched_holds[0].payload["start_time"] == resched_resp.booking.date_time
    assert len(pending_actions) == 2
```

Replace it with:

```python
    # A second Calendar Hold Creator action was queued for the rescheduled booking
    pending_actions = persistence.get_pending_actions()
    resched_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and resched_resp.booking_code in a.payload.get("title", "")]
    assert len(resched_holds) == 1
    assert resched_holds[0].payload["start_time"] == resched_resp.booking.date_time

    resched_docs = [a for a in pending_actions if a.tool_name == "Doc Append" and resched_resp.booking_code in a.payload.get("content", "")]
    assert len(resched_docs) == 1

    resched_emails = [a for a in pending_actions if a.tool_name == "Email Draft Generator" and resched_resp.booking_code in a.payload.get("subject", "")]
    assert len(resched_emails) == 1

    assert len(pending_actions) == 6
```

- [ ] **Step 2: Extend `test_booking_agent_ask_then_book`**

In the same file, find:

```python
    # A Calendar Hold Creator action was queued once the booking was confirmed
    pending_actions = persistence.get_pending_actions()
    book_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and resp_book.booking_code in a.payload.get("title", "")]
    assert len(book_holds) == 1
    assert book_holds[0].payload["start_time"] == resp_book.booking.date_time
```

Replace it with:

```python
    # A Calendar Hold Creator action was queued once the booking was confirmed
    pending_actions = persistence.get_pending_actions()
    book_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and resp_book.booking_code in a.payload.get("title", "")]
    assert len(book_holds) == 1
    assert book_holds[0].payload["start_time"] == resp_book.booking.date_time

    book_docs = [a for a in pending_actions if a.tool_name == "Doc Append" and resp_book.booking_code in a.payload.get("content", "")]
    assert len(book_docs) == 1

    book_emails = [a for a in pending_actions if a.tool_name == "Email Draft Generator" and resp_book.booking_code in a.payload.get("subject", "")]
    assert len(book_emails) == 1

    assert len(pending_actions) == 3
```

- [ ] **Step 3: Extend `test_booking_agent_ask_then_reschedule`**

In the same file, find:

```python
    # A Calendar Hold Creator action was queued for the original booking
    pending_actions = persistence.get_pending_actions()
    old_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and old_code in a.payload.get("title", "")]
    assert len(old_holds) == 1
    assert old_holds[0].payload["start_time"] == old_slot
```

Replace it with:

```python
    # A Calendar Hold Creator action was queued for the original booking
    pending_actions = persistence.get_pending_actions()
    old_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and old_code in a.payload.get("title", "")]
    assert len(old_holds) == 1
    assert old_holds[0].payload["start_time"] == old_slot

    old_docs = [a for a in pending_actions if a.tool_name == "Doc Append" and old_code in a.payload.get("content", "")]
    assert len(old_docs) == 1

    old_emails = [a for a in pending_actions if a.tool_name == "Email Draft Generator" and old_code in a.payload.get("subject", "")]
    assert len(old_emails) == 1
```

Then find:

```python
    # No new Calendar Hold Creator action queued yet — reschedule not confirmed
    assert len(persistence.get_pending_actions()) == 1
```

Replace it with:

```python
    # No new Calendar Hold Creator action queued yet — reschedule not confirmed
    assert len(persistence.get_pending_actions()) == 3
```

Then find:

```python
    # A second Calendar Hold Creator action was queued for the rescheduled booking
    pending_actions = persistence.get_pending_actions()
    new_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and new_code in a.payload.get("title", "")]
    assert len(new_holds) == 1
    assert new_holds[0].payload["start_time"] == resp_resched.booking.date_time
    assert len(pending_actions) == 2
```

Replace it with:

```python
    # A second Calendar Hold Creator action was queued for the rescheduled booking
    pending_actions = persistence.get_pending_actions()
    new_holds = [a for a in pending_actions if a.tool_name == "Calendar Hold Creator" and new_code in a.payload.get("title", "")]
    assert len(new_holds) == 1
    assert new_holds[0].payload["start_time"] == resp_resched.booking.date_time

    new_docs = [a for a in pending_actions if a.tool_name == "Doc Append" and new_code in a.payload.get("content", "")]
    assert len(new_docs) == 1

    new_emails = [a for a in pending_actions if a.tool_name == "Email Draft Generator" and new_code in a.payload.get("subject", "")]
    assert len(new_emails) == 1

    assert len(pending_actions) == 6
```

- [ ] **Step 4: Run the extended tests to verify they fail**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_booking_agent_full_flow src/tests_integration/test_phase3.py::test_booking_agent_ask_then_book src/tests_integration/test_phase3.py::test_booking_agent_ask_then_reschedule -v`
Expected: FAIL — the new `Doc Append`/`Email Draft Generator` assertions find 0 matching actions, and the `len(pending_actions)` counts are still based on Calendar-Hold-only totals (2, 1, 1, 2 instead of 6, 3, 3, 6).

- [ ] **Step 5: Wire `_queue_mcp_followups` into the 4 confirmation call sites**

In `src/Phase3_Voice_Scheduler/booking_agent.py`, there are 4 call sites of
`self._queue_calendar_hold(...)`. Replace each as follows:

1. Inside `_finalize_pending_booking`, RESCHEDULE branch — change:

```python
            self.persistence.set("pending_booking", {})
            self._queue_calendar_hold(booking)

            message = (
                f"Your appointment has been rescheduled. Old booking {old_code} is cancelled. "
```

to:

```python
            self.persistence.set("pending_booking", {})
            self._queue_mcp_followups(booking, top_theme)

            message = (
                f"Your appointment has been rescheduled. Old booking {old_code} is cancelled. "
```

2. Inside `_finalize_pending_booking`, BOOK branch — change:

```python
        self.persistence.set("pending_booking", {})
        self._queue_calendar_hold(booking)

        message = self._book_confirmation_message(new_slot, code, top_theme)
```

to:

```python
        self.persistence.set("pending_booking", {})
        self._queue_mcp_followups(booking, top_theme)

        message = self._book_confirmation_message(new_slot, code, top_theme)
```

3. Inside `handle()`, BOOK with `slot_preference` — change:

```python
                self.persistence.set(code, booking.model_dump())
                self.persistence.set("latest_booking", booking.model_dump())
                self._queue_calendar_hold(booking)

                message = self._book_confirmation_message(slot, code, top_theme)
```

to:

```python
                self.persistence.set(code, booking.model_dump())
                self.persistence.set("latest_booking", booking.model_dump())
                self._queue_mcp_followups(booking, top_theme)

                message = self._book_confirmation_message(slot, code, top_theme)
```

4. Inside `handle()`, RESCHEDULE with `slot_preference` — change:

```python
                self.persistence.set(new_code, new_booking.model_dump())
                self.persistence.set("latest_booking", new_booking.model_dump())
                self._queue_calendar_hold(new_booking)

                message = (
                    f"Your appointment has been rescheduled. Old booking {code_to_reschedule} is cancelled. "
```

to:

```python
                self.persistence.set(new_code, new_booking.model_dump())
                self.persistence.set("latest_booking", new_booking.model_dump())
                self._queue_mcp_followups(new_booking, top_theme)

                message = (
                    f"Your appointment has been rescheduled. Old booking {code_to_reschedule} is cancelled. "
```

- [ ] **Step 6: Run the full Phase 3 test suite**

Run: `python -m pytest src/tests_integration/test_phase3.py -v`
Expected: All tests PASS (23 total, including the 3 new unit tests from Tasks 1-3 and the extended integration tests).

- [ ] **Step 7: Commit**

```bash
git add src/Phase3_Voice_Scheduler/booking_agent.py src/tests_integration/test_phase3.py
git commit -m "feat: queue Doc Append and Email Draft Generator on booking confirmation"
```

---

### Task 5: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest src/tests_integration/test_phase3.py src/tests_integration/test_common.py -v`
Expected: All tests PASS (27 total).

- [ ] **Step 2: Manually inspect a queued Doc Append payload**

Run a quick smoke check that `data/shared_notes.md` does not exist yet (it's
only written when an approved Doc Append action executes — that execution
path is unchanged and already covered by `eval4`):

```bash
python -c "from src.Phase0_Shared_Foundation.config import Config; print(Config.SHARED_NOTES_PATH)"
```

Expected output: `./data/shared_notes.md`
