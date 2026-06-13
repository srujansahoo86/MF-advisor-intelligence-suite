# Voice Booking: Queue Calendar Hold for Approval

## Problem

`BookingAgent` (`src/Phase3_Voice_Scheduler/booking_agent.py`) confirms bookings
and reschedules directly — it never calls `MCPOrchestrator.queue_action(...)`
(`src/Phase4_MCP_Orchestration/orchestrator.py`). As a result, the dashboard's
Approval Center (`/api/actions/pending`) is always empty, regardless of voice
activity. Per the architecture docs
(`Docs/MF_Advisor_Architecture_v2.md`, `Docs/Problemstatement.md`), every
confirmed appointment slot should generate a **"Calendar Hold Creator"**
action that sits in `PENDING` status until a human approves or rejects it —
this human-in-the-loop gate is described as the system's most important
safety property. `queue_action` is currently called only from tests and eval
scripts, never from production code.

The dashboard frontend (`stitch_mf_advisor_intelligence_suite/code.html`) is
already wired to display `"Calendar Hold Creator"` actions and to call
`loadPendingActions()` after every `/api/voice` response — no frontend
changes are needed.

## Goal

When `BookingAgent` confirms a new booking or a reschedule (i.e. it builds a
`Booking` with `status="CONFIRMED"` and persists it as `latest_booking`), it
also queues a `"Calendar Hold Creator"` action via `MCPOrchestrator` so it
appears as a `PENDING` item in the Approval Center. The tool only actually
creates the calendar hold (writes to the `calendar_holds` record) once an
advisor approves it via `/api/actions/approve/{action_id}` — this part of the
flow already works and is unchanged.

This applies to **both BOOK and RESCHEDULE confirmations**, across all 4
confirmation paths in `BookingAgent`:

1. Immediate BOOK (`handle()`, `parsed.slot_preference` present)
2. Finalize BOOK (`_finalize_pending_booking`, `pending["type"] == "BOOK"`)
3. Immediate RESCHEDULE (`handle()`, `parsed.slot_preference` present)
4. Finalize RESCHEDULE (`_finalize_pending_booking`, `pending["type"] == "RESCHEDULE"`)

## Design

### `BookingAgent.__init__` gains an orchestrator

```python
from src.Phase4_MCP_Orchestration.orchestrator import MCPOrchestrator
```

```python
def __init__(self, db_path: str = None):
    self.persistence = Persistence(db_path)
    self.pii_deflector = PIIDeflector()
    self.intent_parser = IntentParser()
    self.slot_manager = SlotManager(db_path)
    self.orchestrator = MCPOrchestrator(db_path)
```

### New helper: `_queue_calendar_hold`

```python
def _queue_calendar_hold(self, booking: Booking) -> None:
    """Queues a Calendar Hold Creator action for advisor approval."""
    self.orchestrator.queue_action("Calendar Hold Creator", {
        "title": f"Advisor Call: {booking.topic} ({booking.booking_code})",
        "start_time": booking.date_time,
        "duration_minutes": 30,
        "attendees": ["advisor@kuvera.in"],
    })
```

- `title` includes the booking code (per Problem Statement: "Tentative
  calendar hold with code in title").
- `start_time` is the confirmed slot string (e.g. `"Wednesday 11:00 AM"`),
  matching `calendar_hold_creator`'s expected format
  (`src/Phase4_MCP_Orchestration/tools.py`).
- `duration_minutes` defaults to `30` (no per-slot duration exists in
  `Config.AVAILABLE_SLOTS`).
- `attendees` is a fixed placeholder `["advisor@kuvera.in"]` (no real
  advisor/client email exists anywhere in this codebase).

### Call sites

Add `self._queue_calendar_hold(booking)` immediately after
`self.persistence.set("latest_booking", booking.model_dump())` at all 4
confirmation paths listed above. No other behavior at those call sites
changes — the booking confirmation message returned to the user is
unaffected; the queued action is a side effect.

### Known limitation

There is no "remove/cancel calendar hold" MCP tool. When a RESCHEDULE cancels
an old booking, any previously-approved hold for the old slot remains in
`calendar_holds` as a stale entry. Fixing this would require a new MCP tool
and is out of scope for this change.

## Testing

Extend `src/tests_integration/test_phase3.py` (Groq-gated where the existing
tests for that flow already are):

1. **Immediate BOOK** (`test_booking_agent_full_flow` or a new assertion in
   it): after a confirmed booking, `orchestrator.list_pending()` (via
   `persistence.get_pending_actions()`) contains a `PENDING`
   `"Calendar Hold Creator"` action whose `payload["start_time"]` matches the
   booked slot and whose `payload["title"]` contains the booking code.

2. **Finalize BOOK** (`test_booking_agent_ask_then_book`): same assertion
   after the follow-up slot-choice message.

3. **Immediate RESCHEDULE**: same assertion after a reschedule with a slot
   preference in the same message — `payload["start_time"]` matches the
   *new* slot and `payload["title"]` contains the *new* booking code.

4. **Finalize RESCHEDULE** (`test_booking_agent_ask_then_reschedule`): same
   assertion after the follow-up slot-choice message.

Each test should also confirm a `"Calendar Hold Creator"` action did **not**
exist before the confirming step (e.g. queue was empty or didn't contain this
action), to confirm the action is queued *as a result of* the confirmation,
not as a pre-existing fixture artifact.
