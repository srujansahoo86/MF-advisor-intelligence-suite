# Voice Scheduler: Ask Before Booking/Rescheduling

## Problem

`BookingAgent.handle()` (`src/Phase3_Voice_Scheduler/booking_agent.py`) handles
`BOOK` and `RESCHEDULE` intents by calling
`SlotManager.resolve(parsed.slot_preference)`. When `slot_preference` is
`None` (the user didn't mention a date/time), `resolve()` silently falls back
to the first available slot (`slot_manager.py:51-52`) and the agent confirms
a booking the user never chose.

Example: "I want to book my appointment" → `intent=BOOK, slot_preference=None`
→ immediate booking into the first open slot, with no clarification.

## Goal

When the user's request doesn't include a date/time:
- **BOOK**: list available slots and ask which one they want. Book only after
  they reply.
- **RESCHEDULE**: list available slots and ask which one they want to move
  to. Only release/cancel the old slot after they reply with a new one.

When the user *does* include a date/time in the same message (e.g. "book a
call for Friday afternoon"), behavior is unchanged — book/reschedule
immediately. This preserves `test_booking_agent_full_flow`.

## Design

### New persisted state: `pending_booking`

Stored via `Persistence` (same key/value store as `latest_booking`), as a
dict. Empty dict `{}` means "no pending booking".

Shape for a pending BOOK:
```json
{"type": "BOOK", "topic": "<topic or 'General Consultation'>"}
```

Shape for a pending RESCHEDULE:
```json
{
  "type": "RESCHEDULE",
  "code_to_reschedule": "KV-XXXX",
  "old_slot": "<slot string>",
  "topic": "<topic from old booking>",
  "prep_notes": "<prep notes from old booking, may be null>"
}
```

### `BookingAgent.handle()` flow

After the existing PII check, intent parse, and top-theme lookup:

1. **If `pending_booking` is non-empty** → this transcript is the user's slot
   choice. Finalize (see "Finalize" below) regardless of what
   `parsed.intent` came back as.

2. **Else if `intent == BOOK`**:
   - If `parsed.slot_preference` is set → resolve & book immediately (today's
     code, unchanged).
   - Else:
     - `available = slot_manager.get_available_slots()`. If empty, return
       "No slots available." (no pending state set).
     - Save `pending_booking = {"type": "BOOK", "topic": parsed.topic or
       "General Consultation"}`.
     - Reply with (optional top-theme line) + a list of available slots +
       "Which one works for you?"

3. **Else if `intent == RESCHEDULE`**:
   - Resolve `code_to_reschedule` and validate it exists / isn't already
     cancelled (today's code, unchanged — error messages unchanged).
   - If `parsed.slot_preference` is set → finalize immediately as today:
     release old slot, cancel old booking, resolve+book new slot, new code.
   - Else:
     - `available = slot_manager.get_available_slots()` (old slot stays
       excluded — it's still marked booked). If empty, return "No slots
       available to reschedule into." (no pending state set, old booking
       untouched).
     - Save `pending_booking = {"type": "RESCHEDULE", "code_to_reschedule":
       ..., "old_slot": old_booking_data["date_time"], "topic":
       old_booking_data["topic"], "prep_notes":
       old_booking_data.get("prep_notes")}`.
     - Reply with available slots + "Which one would you like to move your
       appointment to?"
   - Old booking is **not** modified yet (not cancelled, slot not released)
     — that only happens on finalize, so an abandoned reschedule leaves the
     original booking intact.

4. PREPARE / OTHER branches: unchanged.

### Finalize step (pending_booking non-empty)

- `new_slot = slot_manager.resolve(transcript)` — reuse the existing
  LLM fuzzy-matcher, treating the whole reply as the slot preference.
- `slot_manager.mark_booked(new_slot)`
- `code = self._generate_booking_code()`
- If `pending["type"] == "BOOK"`:
  - Build `Booking(booking_code=code, topic=pending["topic"],
    date_time=new_slot, status="CONFIRMED", top_theme=top_theme,
    prep_notes=None)`
  - Persist under `code` and `latest_booking`.
  - Message: same confirmation format as today's immediate-booking path
    (with top-theme line if `top_theme` is set).
- If `pending["type"] == "RESCHEDULE"`:
  - `slot_manager.release_slot(pending["old_slot"])`
  - Mark `pending["code_to_reschedule"]` booking `CANCELLED` in persistence;
    if it's the `latest_booking`, update that too (today's code, unchanged
    logic, just moved here).
  - Build `Booking(booking_code=code, topic=pending["topic"],
    date_time=new_slot, status="CONFIRMED", top_theme=top_theme,
    prep_notes=pending["prep_notes"])`
  - Persist under `code` and `latest_booking`.
  - Message: same "rescheduled" confirmation format as today's immediate
    path.
- Clear `pending_booking` (set to `{}`).
- Return `AgentResponse(message=..., booking=booking, booking_code=code,
  top_theme=top_theme)`.

### Known limitation

If `pending_booking` is set and the user's reply doesn't clearly name a slot
(e.g. they ask an unrelated question), `slot_manager.resolve()` falls back to
the first available slot and that gets booked/rescheduled-into. This is the
same fallback `resolve()` already used today — we're just deferring it by one
turn. Improving this would require a confidence signal from the LLM matcher
and is out of scope for this fix.

## Testing

Add to `src/tests_integration/test_phase3.py` (Groq-gated, following existing
`@skip_no_groq` pattern):

1. **BOOK without slot preference** → `adapter.process("I want to book my
   appointment")`:
   - `resp.booking is None`, `resp.booking_code is None`
   - message mentions at least one slot from `Config.AVAILABLE_SLOTS` and
     asks the user to choose
   - `persistence.get("pending_booking")["type"] == "BOOK"`
   - Follow-up `adapter.process("Monday 10 AM")` →
     - `resp.booking is not None`, `status == "CONFIRMED"`
     - `persistence.get("pending_booking") == {}`
     - the chosen slot is marked booked via `SlotManager`

2. **RESCHEDULE without slot preference**:
   - First book a slot (existing helper flow).
   - `adapter.process(f"Can I reschedule {code}?")` (no date/time) →
     - `resp.booking is None`
     - message lists available slots
     - old booking (`code`) still `CONFIRMED`, old slot still marked booked
     - `persistence.get("pending_booking")["type"] == "RESCHEDULE"`
   - Follow-up with a slot reply →
     - new booking `CONFIRMED` with a new code
     - old booking now `CANCELLED`, old slot released
     - new slot marked booked
     - `pending_booking` cleared

Existing tests (`test_slot_manager_returns_valid_slot`,
`test_booking_agent_full_flow`) are unaffected since both go through the
"slot preference present" immediate path.
