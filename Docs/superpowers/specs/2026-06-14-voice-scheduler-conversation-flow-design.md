# Voice Scheduler: Conversational Session Flow + Booking Fixes

## Problem

The voice scheduler (`src/Phase3_Voice_Scheduler/`) currently has two bugs and
is missing a proper conversation lifecycle:

1. **Books without offering options.** `BookingAgent.handle()`
   (`booking_agent.py`) only asks the user to pick a slot when
   `IntentParser.parse()` returns `slot_preference=None`. The LLM-based
   parser occasionally returns a non-null `slot_preference` even when the
   user never mentioned a day/time, sending the request down the
   immediate-booking path (`booking_agent.py:178-199`) and skipping the
   "which slot works for you?" step entirely.

2. **"No slots available" after a few bookings.** `Config.AVAILABLE_SLOTS`
   (`config.py:25-31`) is a fixed list of 10 weekday+time labels.
   `SlotManager` marks a label as permanently booked in SQLite
   (`slot_manager.py`) with no expiry, so after ~10 bookings
   `get_available_slots()` returns `[]` forever.

3. **No session lifecycle.** Pressing the mic immediately starts listening
   for a command. There's no greeting, no explanation of what the assistant
   can do, and no graceful way to end the conversation — the user just stops
   talking.

## Goal

- On the first mic press of a session, the agent greets the user
  (time-of-day based: "Good morning/afternoon/evening"), briefly explains
  its capabilities (book / reschedule / prepare for advisor appointments),
  then starts listening.
- The user can end the conversation by saying a goodbye phrase ("bye",
  "that's all", etc.) at any point — including mid-booking — and the agent
  responds with a thank-you/closing message and stops listening until the
  mic is pressed again (which restarts the greeting).
- Fix Bug 1: discard a hallucinated `slot_preference` when the transcript
  contains no actual day/time words, forcing the "ask for options" path.
- Fix Bug 2: make slot availability roll forward week-to-week instead of
  permanently exhausting a fixed pool.

Existing tests (`test_booking_agent_full_flow`,
`test_booking_agent_ask_then_book`, `test_booking_agent_ask_then_reschedule`,
`test_booking_agent_reasks_on_unmatched_slot_reply`,
`test_slot_manager_returns_valid_slot`) must continue to pass — slot *labels*
(`Config.AVAILABLE_SLOTS`, `Booking.date_time`) are unchanged.

## Design

### 1. Frontend session lifecycle (`stitch_mf_advisor_intelligence_suite/code.html`)

New state:
```js
let sessionActive = false;
```

New helper:
```js
function getTimeGreeting() {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
}
```

New constant capabilities-intro template (static text, no backend call):
```
"<Good morning/afternoon/evening>! I'm your Kuvera voice scheduling
assistant. I can help you book an advisor appointment, reschedule an
existing one, or tell you what to prepare for your call. What would you
like to do?"
```

Mic button handler (`micButton.addEventListener('click', ...)`):

- If `!sessionActive`:
  - Cancel any in-progress speech (existing barge-in behavior).
  - Build the greeting string via `getTimeGreeting()`.
  - Set `sessionActive = true`.
  - Speak the greeting via `SpeechSynthesisUtterance`. On `utterance.onend`,
    call `listenAfterSpeechEnds()` (existing helper) to auto-open the mic —
    same pattern already used for slot-choice follow-ups.
  - Update `transcriptText` to show the greeting text.
  - Do **not** call `recognition.start()` synchronously and do **not** hit
    `/api/voice` for this turn.
- Else (session already active): unchanged — start/stop `recognition` as
  today.

`sendVoiceTranscript()` response handling:

- New field `data.session_ended` (boolean) from `/api/voice`.
- If `data.session_ended === true`:
  - Speak `data.message` (the closing line) as today.
  - Do **not** set `awaitingSlotChoice` / auto-reopen the mic, regardless of
    `data.awaiting_response` (closing messages won't set it, but be
    defensive).
  - Set `sessionActive = false` so the next mic press starts a fresh
    greeting.
  - Update the status text (e.g. "Status: Ready to listen" element at
    `code.html:174`) to indicate the session ended / tap mic to restart.
- Otherwise: unchanged.

Note: the existing requirement that the greeting "dynamically reference the
top theme from the current week's Pulse" is already satisfied by
`_book_confirmation_message` / the BOOK ask-message
(`booking_agent.py:53-64`, `:209-219`) and is unaffected by this change. The
new session-opening greeting is intentionally static/instant so the user
hears something the moment they press the mic, with no backend round trip.

### 2. Backend: goodbye detection → `session_ended`

New module-level helper in `booking_agent.py`:

```python
import re

_GOODBYE_RE = re.compile(
    r"\b(bye|goodbye|good bye|that'?s all|thats all|nothing else|"
    r"no(?:,)? (?:that'?s|thats) (?:all|it)|that'?s it|we'?re done|"
    r"i'?m done|end (?:the )?call|hang up)\b",
    re.IGNORECASE,
)

def _is_goodbye(transcript: str) -> bool:
    return bool(_GOODBYE_RE.search(transcript))
```

`AgentResponse` gains a new field:
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

`BookingAgent.handle()` — new step, after the existing PII check (step 1) and
before the `pending_booking` check (current step 3):

```python
if _is_goodbye(transcript):
    self.persistence.set("pending_booking", {})
    return AgentResponse(
        message="Thank you for calling Kuvera. Have a great day!",
        session_ended=True,
    )
```

This takes priority over `pending_booking` — if the user says "never mind,
bye" while the agent is waiting for a slot choice, the pending booking is
cleared and the call ends cleanly instead of looping on "I didn't catch a
valid slot choice."

`/api/voice` (`src/api/main.py`) — add `session_ended` to the response dict:
```python
return {
    "message": res.message,
    "booking": res.booking.model_dump() if res.booking else None,
    "booking_code": res.booking_code,
    "top_theme": res.top_theme,
    "awaiting_response": res.awaiting_response,
    "session_ended": res.session_ended,
}
```

### 3. Bug 1 fix: discard hallucinated `slot_preference`

New helper in `booking_agent.py`:

```python
_TIME_WORD_RE = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"\d{1,2}(:\d{2})?\s*(am|pm)|morning|afternoon|evening|noon|tonight)\b",
    re.IGNORECASE,
)

def _transcript_mentions_time(transcript: str) -> bool:
    return bool(_TIME_WORD_RE.search(transcript))
```

In `handle()`, immediately after `parsed = self.intent_parser.parse(transcript)`:

```python
if parsed.slot_preference and not _transcript_mentions_time(transcript):
    parsed.slot_preference = None
```

This runs once before the BOOK/RESCHEDULE branches, so both immediate-booking
paths fall back to the existing "ask for options" flow whenever the raw
transcript doesn't actually contain a day/time word — regardless of what the
LLM parser guessed.

### 4. Bug 2 fix: rolling slot availability (`slot_manager.py`)

`Config.AVAILABLE_SLOTS` stays exactly as-is (10 `"<Weekday> <H:MM AM/PM>"`
labels). `SlotManager` changes how `booked_slots` is stored and read.

New helper — computes the ISO date of a label's next upcoming occurrence:

```python
from datetime import datetime, timedelta, date

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def _occurrence_date(self, slot_label: str) -> str:
    weekday_name, time_str = slot_label.split(" ", 1)
    target_weekday = _WEEKDAYS.index(weekday_name)
    slot_time = datetime.strptime(time_str, "%I:%M %p").time()

    now = datetime.now()
    days_ahead = (target_weekday - now.weekday()) % 7
    if days_ahead == 0 and now.time() >= slot_time:
        days_ahead = 7
    return (now + timedelta(days=days_ahead)).date().isoformat()
```

`booked_slots` persistence shape changes from `list[str]` to
`list[{"slot": str, "date": "YYYY-MM-DD"}]`. `get_booked_slots()` reads,
**prunes expired entries** (date < today), and persists the pruned list:

```python
def get_booked_slots(self) -> list[dict]:
    booked = self.persistence.get("booked_slots")
    if not booked or not isinstance(booked, list):
        return []
    today = date.today().isoformat()
    valid = [b for b in booked if isinstance(b, dict) and b.get("date", "") >= today]
    if valid != booked:
        self.persistence.set("booked_slots", valid)
    return valid
```

`is_available`, `mark_booked`, `release_slot` operate on the `"slot"` field
only (label matching, as before) but read/write the new dict shape:

```python
def is_available(self, slot: str) -> bool:
    return not any(b["slot"] == slot for b in self.get_booked_slots())

def mark_booked(self, slot: str) -> None:
    booked = self.get_booked_slots()
    if not any(b["slot"] == slot for b in booked):
        booked.append({"slot": slot, "date": self._occurrence_date(slot)})
        self.persistence.set("booked_slots", booked)

def release_slot(self, slot: str) -> None:
    booked = self.get_booked_slots()
    filtered = [b for b in booked if b["slot"] != slot]
    if filtered != booked:
        self.persistence.set("booked_slots", filtered)
```

`get_available_slots()` and `resolve()` / `match_pending_reply()` are
**unchanged** — they still operate on `Config.AVAILABLE_SLOTS` labels and the
LLM-matching prompts.

**Migration note:** any pre-existing `booked_slots` value in `data/app.db`
is the old `list[str]` shape. `get_booked_slots()`'s `isinstance(b, dict)`
filter drops those legacy string entries on first read (treated as expired),
so old test/demo bookings are effectively released once. This is a one-time,
backward-only effect with no impact on `Booking` records already stored
under their own keys (`KV-XXXX`, `latest_booking`).

## Known limitations

- The session-start greeting is static and client-side; it does not call the
  backend, so it cannot reference live data (e.g. top theme). That dynamic
  reference continues to happen later, in the BOOK ask/confirmation message,
  as today.
- Goodbye detection is keyword/regex-based, not LLM-based — phrasing outside
  the listed patterns (e.g. "I think that covers it") won't end the session.
  This mirrors the existing deterministic style used by `PIIDeflector` and
  keeps behavior predictable/testable without an extra LLM call.
- `_occurrence_date` uses the server's local clock for "has this week's slot
  time already passed" — for a single-advisor demo deployment this is
  acceptable; a multi-timezone production system would need per-user
  timezone handling.

## Testing

Add to `src/tests_integration/test_phase3.py`:

1. **Goodbye ends session** — `adapter.process("Thanks, that's all, bye")`
   (no Groq needed, pure regex):
   - `resp.session_ended is True`
   - message is non-empty (closing message)
   - `persistence.get("pending_booking") == {}`

2. **Goodbye mid-pending-booking** — start a BOOK with no slot preference
   (`pending_booking` set), then send a goodbye transcript:
   - `resp.session_ended is True`
   - `persistence.get("pending_booking") == {}`
   - no booking was created

3. **Bug 1 guard (unit-level, no Groq)** — call
   `_transcript_mentions_time(...)` directly with:
   - `"I want to book my appointment"` → `False`
   - `"book a call for Monday morning"` → `True`
   - `"can we do this at 3pm"` → `True`

4. **Bug 2 rolling slots (no Groq)** — using `SlotManager` directly with
   `clean_db`:
   - `mark_booked("Monday 10:00 AM")` → `is_available("Monday 10:00 AM")
     is False`
   - Manually write a `booked_slots` entry with `date` in the past →
     `get_available_slots()` includes `"Monday 10:00 AM"` again (pruned).

5. **Legacy data migration (no Groq)** — write `booked_slots` as the old
   `list[str]` shape directly via `persistence.set(...)`, then call
   `get_booked_slots()` → returns `[]` and persists `[]`.

Existing LLM-gated tests (`test_booking_agent_full_flow`,
`test_booking_agent_ask_then_book`, `test_booking_agent_ask_then_reschedule`,
`test_booking_agent_reasks_on_unmatched_slot_reply`,
`test_slot_manager_returns_valid_slot`) require no changes since slot labels
and `Booking.date_time` values are unchanged.
