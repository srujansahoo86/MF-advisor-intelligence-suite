# Voice Scheduler Conversation Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a greet → explain-capabilities → converse → goodbye session
lifecycle to the voice scheduler, and fix the two underlying booking bugs
(books without offering slot options; slot pool permanently exhausts).

**Architecture:** Two deterministic regex guards added to
`BookingAgent.handle()` (one discards a hallucinated `slot_preference`, one
detects goodbye phrases and ends the session via a new `session_ended` flag
on `AgentResponse`), a rolling-date rewrite of `SlotManager`'s
`booked_slots` storage, an `/api/voice` passthrough of `session_ended`, and a
frontend session-state wrapper in `code.html` that speaks a time-based
greeting + capability intro on the first mic press and stops auto-listening
once `session_ended` is true.

**Tech Stack:** Python 3.12, FastAPI, pytest, vanilla JS + Web Speech API
(SpeechRecognition / SpeechSynthesis).

---

## Reference: design spec

Full design and rationale:
`Docs/superpowers/specs/2026-06-14-voice-scheduler-conversation-flow-design.md`

---

### Task 1: Discard hallucinated `slot_preference` (Bug 1)

**Files:**
- Modify: `src/Phase3_Voice_Scheduler/booking_agent.py`
- Test: `src/tests_integration/test_phase3.py`

- [ ] **Step 1: Write the failing unit test for the time-word detector**

Add to `src/tests_integration/test_phase3.py`, after the existing imports
(do not remove anything):

```python
from unittest.mock import patch
from src.Phase3_Voice_Scheduler.intent_parser import ParsedIntent
from src.Phase3_Voice_Scheduler.booking_agent import (
    _transcript_mentions_time,
    _is_goodbye,
)
```

Then add this test near the other slot-manager tests:

```python
# 14. Time-word detector used to guard against hallucinated slot_preference
def test_transcript_mentions_time_detects_day_and_time_words():
    assert _transcript_mentions_time("book a call for Monday morning") is True
    assert _transcript_mentions_time("can we do this at 3pm") is True
    assert _transcript_mentions_time("can we do this at 3 PM") is True
    assert _transcript_mentions_time("I want to book my appointment") is False
    assert _transcript_mentions_time("") is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_transcript_mentions_time_detects_day_and_time_words -v`

Expected: FAIL with `ImportError` / `ModuleNotFoundError` — `_transcript_mentions_time` and `_is_goodbye` don't exist yet.

- [ ] **Step 3: Add the time-word regex + helper to `booking_agent.py`**

Open `src/Phase3_Voice_Scheduler/booking_agent.py`. After the existing
imports (the block ending with
`from src.Phase4_MCP_Orchestration.orchestrator import MCPOrchestrator`),
add:

```python

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
```

(`_is_goodbye` is added now alongside `_transcript_mentions_time` so Task 1's
import in the test file resolves; it's wired into `handle()` in Task 2.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_transcript_mentions_time_detects_day_and_time_words -v`

Expected: PASS

- [ ] **Step 5: Write the failing integration test for the guard in `handle()`**

Add to `src/tests_integration/test_phase3.py`:

```python
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
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_handle_discards_hallucinated_slot_preference -v`

Expected: FAIL — `resp.booking is not None` (the agent booked immediately
using the mocked `slot_preference`, even though the transcript has no
day/time words).

- [ ] **Step 7: Add the guard to `handle()`**

In `src/Phase3_Voice_Scheduler/booking_agent.py`, find:

```python
        # 4. Parse Intent
        parsed = self.intent_parser.parse(transcript)

        # 5. Handle Intents
        if parsed.intent == "BOOK":
```

Replace with:

```python
        # 4. Parse Intent
        parsed = self.intent_parser.parse(transcript)

        # Guard against the LLM hallucinating a slot_preference when the user
        # never actually mentioned a day/time — force the ask-for-options flow.
        if parsed.slot_preference and not _transcript_mentions_time(transcript):
            parsed.slot_preference = None

        # 5. Handle Intents
        if parsed.intent == "BOOK":
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_handle_discards_hallucinated_slot_preference -v`

Expected: PASS

- [ ] **Step 9: Run the full Phase 3 test file**

Run: `python -m pytest src/tests_integration/test_phase3.py -v`

Expected: all non-Groq tests PASS (Groq-gated tests skip if `GROQ_API_KEY`
is unset).

- [ ] **Step 10: Commit**

```bash
git add src/Phase3_Voice_Scheduler/booking_agent.py src/tests_integration/test_phase3.py
git commit -m "fix: discard hallucinated slot_preference when transcript has no day/time words"
```

---

### Task 2: Goodbye detection + `session_ended`

**Files:**
- Modify: `src/Phase3_Voice_Scheduler/booking_agent.py`
- Test: `src/tests_integration/test_phase3.py`

- [ ] **Step 1: Write the failing test for a simple goodbye**

Add to `src/tests_integration/test_phase3.py`:

```python
# 16. A goodbye phrase ends the session immediately (no LLM needed)
def test_goodbye_ends_session(clean_db):
    adapter = VoiceAdapter(db_path=clean_db)
    resp = adapter.process("Thanks, that's all, bye")

    assert resp.session_ended is True
    assert resp.message != ""
    assert resp.booking is None

    assert Persistence(clean_db).get("pending_booking") == {}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_goodbye_ends_session -v`

Expected: FAIL with `AttributeError: 'AgentResponse' object has no attribute 'session_ended'`

- [ ] **Step 3: Add `session_ended` to `AgentResponse` and wire `_is_goodbye` into `handle()`**

In `src/Phase3_Voice_Scheduler/booking_agent.py`, find:

```python
@dataclass
class AgentResponse:
    message: str
    booking: Optional[Booking] = None
    booking_code: Optional[str] = None
    top_theme: Optional[str] = None
    awaiting_response: bool = False
```

Replace with:

```python
@dataclass
class AgentResponse:
    message: str
    booking: Optional[Booking] = None
    booking_code: Optional[str] = None
    top_theme: Optional[str] = None
    awaiting_response: bool = False
    session_ended: bool = False
```

Then find the start of `handle()`:

```python
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
```

Replace with:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_goodbye_ends_session -v`

Expected: PASS

- [ ] **Step 5: Write the failing test for goodbye mid-pending-booking (Groq-gated)**

Add to `src/tests_integration/test_phase3.py`:

```python
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
```

- [ ] **Step 6: Run the test**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_goodbye_mid_pending_booking -v`

Expected: PASS (or SKIPPED if `GROQ_API_KEY` is not set — that's fine, the
goodbye check runs before `_finalize_pending_booking` per the Step 3 ordering
and doesn't depend on the LLM).

- [ ] **Step 7: Run the full Phase 3 test file**

Run: `python -m pytest src/tests_integration/test_phase3.py -v`

Expected: all non-Groq tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/Phase3_Voice_Scheduler/booking_agent.py src/tests_integration/test_phase3.py
git commit -m "feat: detect goodbye phrases and end voice scheduler session"
```

---

### Task 3: `/api/voice` passes through `session_ended`

**Files:**
- Modify: `src/api/main.py`
- Test: `src/tests_integration/test_phase5.py`

- [ ] **Step 1: Write the failing test**

Add to `src/tests_integration/test_phase5.py`, after `test_api_voice_booking`:

```python
# 4b. Voice scheduler reports session_ended on a goodbye (no LLM needed)
def test_api_voice_session_ended(clean_env):
    client = clean_env

    res = client.post("/api/voice", json={"transcript": "Thanks, that's all, bye"})
    assert res.status_code == 200
    data = res.json()
    assert data["session_ended"] is True
    assert data["booking"] is None
    assert data["message"] != ""
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest src/tests_integration/test_phase5.py::test_api_voice_session_ended -v`

Expected: FAIL — `data["session_ended"]` raises `KeyError` (key not present
in the response yet).

- [ ] **Step 3: Add `session_ended` to the `/api/voice` response**

In `src/api/main.py`, find:

```python
@app.post("/api/voice")
def process_voice_transcript(req: TranscriptRequest):
    try:
        adapter = VoiceAdapter()
        res = adapter.process(req.transcript)
        # Convert dataclass/dict to response dict
        return {
            "message": res.message,
            "booking": res.booking.model_dump() if res.booking else None,
            "booking_code": res.booking_code,
            "top_theme": res.top_theme,
            "awaiting_response": res.awaiting_response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Replace with:

```python
@app.post("/api/voice")
def process_voice_transcript(req: TranscriptRequest):
    try:
        adapter = VoiceAdapter()
        res = adapter.process(req.transcript)
        # Convert dataclass/dict to response dict
        return {
            "message": res.message,
            "booking": res.booking.model_dump() if res.booking else None,
            "booking_code": res.booking_code,
            "top_theme": res.top_theme,
            "awaiting_response": res.awaiting_response,
            "session_ended": res.session_ended
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest src/tests_integration/test_phase5.py::test_api_voice_session_ended -v`

Expected: PASS

- [ ] **Step 5: Run the full Phase 5 test file**

Run: `python -m pytest src/tests_integration/test_phase5.py -v`

Expected: all non-Groq tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api/main.py src/tests_integration/test_phase5.py
git commit -m "feat: expose session_ended on /api/voice"
```

---

### Task 4: Rolling slot availability (Bug 2)

**Files:**
- Modify: `src/Phase3_Voice_Scheduler/slot_manager.py`
- Test: `src/tests_integration/test_phase3.py`

- [ ] **Step 1: Write the failing tests**

Add to `src/tests_integration/test_phase3.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_slot_manager_rolling_availability src/tests_integration/test_phase3.py::test_slot_manager_prunes_expired_bookings src/tests_integration/test_phase3.py::test_slot_manager_ignores_legacy_string_entries -v`

Expected:
- `test_slot_manager_rolling_availability` PASSES already (current
  implementation happens to satisfy it) — note this, it will still pass
  after the rewrite.
- `test_slot_manager_prunes_expired_bookings` FAILS on its last line,
  `assert persistence.get("booked_slots") == []`. The old
  `get_booked_slots()` returns whatever was stored without pruning, so
  `persistence.get("booked_slots")` still holds the manually-set
  `[{"slot": "Tuesday 3:00 PM", "date": "2000-01-01"}]` instead of `[]`.
  (The earlier `is_available`/`get_available_slots` assertions happen to
  pass even on old code, since the old `slot not in booked` check compares
  a string against a list-of-dicts and is always `True` — that's the bug
  this rewrite fixes properly.)
- `test_slot_manager_ignores_legacy_string_entries` FAILS —
  `get_booked_slots()` currently returns the raw list `["Monday 10:00 AM",
  "Friday 3:00 PM"]` unchanged, not `[]`.

- [ ] **Step 3: Rewrite `slot_manager.py`'s storage methods**

Open `src/Phase3_Voice_Scheduler/slot_manager.py`. At the top, find:

```python
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
```

Replace with:

```python
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
```

The rest of `slot_manager.py` (`resolve` and `match_pending_reply`) is
unchanged — leave it as-is below the replaced block.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest src/tests_integration/test_phase3.py::test_slot_manager_rolling_availability src/tests_integration/test_phase3.py::test_slot_manager_prunes_expired_bookings src/tests_integration/test_phase3.py::test_slot_manager_ignores_legacy_string_entries -v`

Expected: all 3 PASS

- [ ] **Step 5: Run the full Phase 3 test file**

Run: `python -m pytest src/tests_integration/test_phase3.py -v`

Expected: all non-Groq tests PASS, including
`test_slot_manager_returns_valid_slot`,
`test_booking_agent_full_flow` (if Groq key present), etc.

- [ ] **Step 6: Commit**

```bash
git add src/Phase3_Voice_Scheduler/slot_manager.py src/tests_integration/test_phase3.py
git commit -m "fix: roll slot availability forward by date instead of permanent exhaustion"
```

---

### Task 5: Frontend session lifecycle (greeting → capabilities → conversation → goodbye)

**Files:**
- Modify: `stitch_mf_advisor_intelligence_suite/code.html`

This task has no automated test (the file is static HTML/JS with no test
harness). Verification is manual in Task 6.

- [ ] **Step 1: Add an id to the status text span**

In `stitch_mf_advisor_intelligence_suite/code.html`, find (around line 174):

```html
<span class="text-xs font-mono-data text-on-surface-variant uppercase tracking-widest pb-1">Status: Ready to listen</span>
```

Replace with:

```html
<span class="text-xs font-mono-data text-on-surface-variant uppercase tracking-widest pb-1" id="voice-status-text">Status: Ready to listen</span>
```

- [ ] **Step 2: Add `sessionActive` state and the status element lookup**

Find (around line 633-637):

```js
    // --- 3. Voice Scheduler Integration ---
    const micButton = document.getElementById('mic-button');
    const transcriptText = document.getElementById('transcript-text');
    const bookingCodeBadge = document.getElementById('booking-code-badge');
    let isListening = false;
    let recognition = null;
```

Replace with:

```js
    // --- 3. Voice Scheduler Integration ---
    const micButton = document.getElementById('mic-button');
    const transcriptText = document.getElementById('transcript-text');
    const bookingCodeBadge = document.getElementById('booking-code-badge');
    const voiceStatusText = document.getElementById('voice-status-text');
    let isListening = false;
    let recognition = null;

    // Tracks whether the greeting/capabilities intro has been spoken for the
    // current session. Reset to false once the agent ends the call
    // (session_ended), so the next mic press starts a fresh greeting.
    let sessionActive = false;
```

- [ ] **Step 3: Add the greeting helper functions**

Find (around line 651-655, right after `MIC_RESTART_DELAY_MS`):

```js
    const MIC_RESTART_DELAY_MS = 700;

    function normalizeForCompare(s) {
```

Replace with:

```js
    const MIC_RESTART_DELAY_MS = 700;

    // Picks a time-of-day greeting based on the user's device clock.
    function getTimeGreeting() {
        const h = new Date().getHours();
        if (h < 12) return "Good morning";
        if (h < 17) return "Good afternoon";
        return "Good evening";
    }

    // Builds the static session-opening greeting + capabilities intro.
    function buildGreetingMessage() {
        return `${getTimeGreeting()}! I'm your Kuvera voice scheduling assistant. ` +
            `I can help you book an advisor appointment, reschedule an existing one, ` +
            `or tell you what to prepare for your call. What would you like to do?`;
    }

    function normalizeForCompare(s) {
```

- [ ] **Step 4: Update the mic button click handler**

Find (around line 733-752):

```js
    micButton.addEventListener('click', () => {
        if (SpeechRecognition) {
            if (isListening) {
                recognition.stop();
            } else {
                // Barge-in: cut off the assistant's speech if the user
                // taps the mic while it is still talking.
                if (window.speechSynthesis && window.speechSynthesis.speaking) {
                    window.speechSynthesis.cancel();
                }
                recognition.start();
            }
        } else {
            const typed = prompt("Speech recognition is not supported in this browser. Please type your scheduling command:");
            if (typed && typed.trim()) {
                transcriptText.textContent = `"${typed}"`;
                sendVoiceTranscript(typed);
            }
        }
    });
```

Replace with:

```js
    micButton.addEventListener('click', () => {
        // First press of a session: speak the greeting + capabilities intro,
        // then auto-open the mic once it finishes (no backend call yet).
        if (!sessionActive) {
            sessionActive = true;

            if (window.speechSynthesis && window.speechSynthesis.speaking) {
                window.speechSynthesis.cancel();
            }

            const greeting = buildGreetingMessage();
            transcriptText.textContent = greeting;
            if (voiceStatusText) voiceStatusText.textContent = "Status: Greeting...";

            if ('speechSynthesis' in window) {
                const utterance = new SpeechSynthesisUtterance(greeting);
                if (SpeechRecognition && recognition) {
                    utterance.onend = () => {
                        if (voiceStatusText) voiceStatusText.textContent = "Status: Listening...";
                        listenAfterSpeechEnds();
                    };
                }
                window.speechSynthesis.speak(utterance);
            } else if (SpeechRecognition && recognition) {
                recognition.start();
            }
            return;
        }

        if (SpeechRecognition) {
            if (isListening) {
                recognition.stop();
            } else {
                // Barge-in: cut off the assistant's speech if the user
                // taps the mic while it is still talking.
                if (window.speechSynthesis && window.speechSynthesis.speaking) {
                    window.speechSynthesis.cancel();
                }
                recognition.start();
            }
        } else {
            const typed = prompt("Speech recognition is not supported in this browser. Please type your scheduling command:");
            if (typed && typed.trim()) {
                transcriptText.textContent = `"${typed}"`;
                sendVoiceTranscript(typed);
            }
        }
    });
```

- [ ] **Step 5: Handle `session_ended` in `sendVoiceTranscript`**

Find (around line 770-791):

```js
                if (data.booking_code) {
                    bookingCodeBadge.textContent = `Booking Code: ${data.booking_code}`;
                }

                // Read confirmation back aloud (TTS)
                if ('speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                    const utterance = new SpeechSynthesisUtterance(data.message);

                    // If the assistant is asking a follow-up question (e.g. "Which
                    // slot works for you?"), keep the conversation going: re-open
                    // the mic automatically once the assistant finishes speaking,
                    // so the user doesn't have to press the mic button again.
                    if (data.awaiting_response && recognition) {
                        awaitingSlotChoice = true;
                        lastSpokenMessage = data.message;
                        utterance.onend = () => {
                            listenAfterSpeechEnds();
                        };
                    } else {
                        awaitingSlotChoice = false;
                        lastSpokenMessage = "";
                    }

                    window.speechSynthesis.speak(utterance);
                }
```

Replace with:

```js
                if (data.booking_code) {
                    bookingCodeBadge.textContent = `Booking Code: ${data.booking_code}`;
                }

                if (data.session_ended) {
                    sessionActive = false;
                    if (voiceStatusText) voiceStatusText.textContent = "Status: Call ended — tap mic to start again";
                }

                // Read confirmation back aloud (TTS)
                if ('speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                    const utterance = new SpeechSynthesisUtterance(data.message);

                    // If the assistant is asking a follow-up question (e.g. "Which
                    // slot works for you?"), keep the conversation going: re-open
                    // the mic automatically once the assistant finishes speaking,
                    // so the user doesn't have to press the mic button again.
                    // Never auto-reopen once the agent has said goodbye.
                    if (data.awaiting_response && !data.session_ended && recognition) {
                        awaitingSlotChoice = true;
                        lastSpokenMessage = data.message;
                        utterance.onend = () => {
                            listenAfterSpeechEnds();
                        };
                    } else {
                        awaitingSlotChoice = false;
                        lastSpokenMessage = "";
                        if (data.session_ended) {
                            utterance.onend = () => {
                                if (voiceStatusText) voiceStatusText.textContent = "Status: Call ended — tap mic to start again";
                            };
                        }
                    }

                    window.speechSynthesis.speak(utterance);
                }
```

- [ ] **Step 6: Also reset `voiceStatusText` when listening starts/stops normally**

Find `recognition.onstart` and `recognition.onend` (around line 696-709):

```js
        recognition.onstart = () => {
            isListening = true;
            micButton.classList.remove('pulse-primary');
            micButton.classList.add('animate-pulse', 'bg-error', 'text-on-error');
            transcriptText.textContent = "Listening to your request...";
            transcriptText.classList.add('animate-pulse');
        };

        recognition.onend = () => {
            isListening = false;
            micButton.classList.add('pulse-primary');
            micButton.classList.remove('animate-pulse', 'bg-error', 'text-on-error');
            transcriptText.classList.remove('animate-pulse');
        };
```

Replace with:

```js
        recognition.onstart = () => {
            isListening = true;
            micButton.classList.remove('pulse-primary');
            micButton.classList.add('animate-pulse', 'bg-error', 'text-on-error');
            transcriptText.textContent = "Listening to your request...";
            transcriptText.classList.add('animate-pulse');
            if (voiceStatusText) voiceStatusText.textContent = "Status: Listening...";
        };

        recognition.onend = () => {
            isListening = false;
            micButton.classList.add('pulse-primary');
            micButton.classList.remove('animate-pulse', 'bg-error', 'text-on-error');
            transcriptText.classList.remove('animate-pulse');
            if (voiceStatusText && sessionActive) voiceStatusText.textContent = "Status: Ready to listen";
        };
```

- [ ] **Step 7: Commit**

```bash
git add stitch_mf_advisor_intelligence_suite/code.html
git commit -m "feat: add greeting/capabilities intro and goodbye handling to voice UI"
```

---

### Task 6: Full test suite + manual end-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `python -m pytest src/tests_integration -v`

Expected: all non-Groq tests PASS. If `GROQ_API_KEY` is set, all tests PASS.

- [ ] **Step 2: Start the API server**

Run (from project root, in the background):
`python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload`

- [ ] **Step 3: Manual browser verification**

Open `http://127.0.0.1:8000/` in a browser (Chrome/Edge recommended for
Web Speech API support) and verify:

1. Press the mic button. The agent should speak a greeting matching your
   local time of day ("Good morning/afternoon/evening! I'm your Kuvera
   voice scheduling assistant...") and then automatically start listening
   (status text changes to "Status: Listening...").
2. Say "I want to book a call about my SIP mandate" (no day/time mentioned).
   The agent should list available slots and ask which one you want — it
   must NOT book immediately. Confirms Bug 1 fix.
3. Say one of the listed slots (e.g. "Monday 10 AM"). The agent should
   confirm the booking with a Booking Code, and the booking code badge
   should update.
4. Press the mic again and repeat steps 2-3 for a second booking. Confirm
   slots are still being offered (not "No slots available") — confirms
   Bug 2 fix is in effect for the remaining pool.
5. Say "Thanks, that's all, bye". The agent should reply with a thank-you/
   closing message, the status text should show "Status: Call ended — tap
   mic to start again", and the mic should NOT automatically reopen.
6. Press the mic again — the full greeting + capabilities intro should play
   again from the top (new session).

- [ ] **Step 4: Stop the server**

Find and stop the `uvicorn` process started in Step 2 (Windows:
`netstat -ano | findstr :8000` then `taskkill //PID <pid> //F`).
