# Voice Booking: Queue Doc Append and Email Draft Generator Alongside Calendar Hold

## Problem

`BookingAgent` (`src/Phase3_Voice_Scheduler/booking_agent.py`) currently queues
only a `"Calendar Hold Creator"` action when a booking/reschedule is confirmed
(via `_queue_calendar_hold`, added in a prior change). The Problem Statement
(`Docs/Problemstatement.md`) and architecture doc
(`Docs/MF_Advisor_Architecture_v2.md`) require **at least three MCP tools** in
the orchestration layer, all reachable through the Approval Centre:

| Tool | Inputs | Output |
|------|--------|--------|
| Notes / Doc Append | date, top themes, pulse, fee explainer, booking code | Appended entry in shared doc |
| Calendar Hold Creator | topic, slot, booking code | Tentative calendar hold with code in title |
| Email Draft Generator | advisor details, pulse snippet, booking code | Draft email with market context — no auto-send |

`Doc Append` and `Email Draft Generator` are implemented in
`src/Phase4_MCP_Orchestration/tools.py` and exercised by `eval4`/`eval5` with
hand-built payloads, but nothing in the live application ever calls
`queue_action("Doc Append", ...)` or `queue_action("Email Draft Generator",
...)`. In a real demo, the Approval Centre only ever shows `"Calendar Hold
Creator"` entries from actual voice usage — the other two required tools are
never demonstrated end-to-end.

## Goal

When `BookingAgent` confirms a new booking or reschedule (the same 4
confirmation paths that already call `_queue_calendar_hold`), it also queues:

1. A `"Doc Append"` action that appends a dated markdown entry (top theme,
   pulse key observation, fee explainer last-checked date, booking code,
   topic, slot) to a shared notes file.
2. An `"Email Draft Generator"` action addressed to the advisor, referencing
   the booking topic and code, which (once approved) pulls a RAG market-context
   snippet via the existing `email_draft_generator` tool.

This applies to all 4 confirmation paths in `BookingAgent`:

1. Immediate BOOK (`handle()`, `parsed.slot_preference` present)
2. Finalize BOOK (`_finalize_pending_booking`, `pending["type"] == "BOOK"`)
3. Immediate RESCHEDULE (`handle()`, `parsed.slot_preference` present)
4. Finalize RESCHEDULE (`_finalize_pending_booking`, `pending["type"] == "RESCHEDULE"`)

## Design

### New Config constant

`src/Phase0_Shared_Foundation/config.py`:

```python
# Phase 3/4 — shared notes doc appended to by the Doc Append MCP tool
SHARED_NOTES_PATH = os.getenv("SHARED_NOTES_PATH", "./data/shared_notes.md")
```

### New imports in `booking_agent.py`

```python
from datetime import date
from src.Phase0_Shared_Foundation.config import Config
```

### New helper: `_queue_doc_append`

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

- Only `top_theme`, `Pulse Observation`, and `Fee Explainer` lines are included
  when that data actually exists in persistence — no hallucinated fields.
- `content` ends with a blank line so consecutive appended entries are
  visually separated in the markdown file.

### New helper: `_queue_email_draft`

```python
def _queue_email_draft(self, booking: Booking) -> None:
    """Queues an Email Draft Generator action for advisor approval."""
    self.orchestrator.queue_action("Email Draft Generator", {
        "recipient": "advisor@kuvera.in",
        "subject": f"Pre-meeting brief: {booking.topic} ({booking.booking_code})",
        "topic": booking.topic,
    })
```

- `recipient` matches the placeholder advisor address already used by
  `_queue_calendar_hold`'s `attendees`.
- `topic` is passed through to `email_draft_generator` (existing tool), which
  queries the Phase 1 RAG engine for a market-context snippet on that topic —
  satisfying "Market Context in email draft" without any change to `tools.py`.

### New helper: `_queue_mcp_followups`

```python
def _queue_mcp_followups(self, booking: Booking, top_theme: Optional[str]) -> None:
    """Queues all required MCP actions for a confirmed booking/reschedule."""
    self._queue_calendar_hold(booking)
    self._queue_doc_append(booking, top_theme)
    self._queue_email_draft(booking)
```

### Call sites

Replace each of the 4 existing `self._queue_calendar_hold(booking)` calls with
`self._queue_mcp_followups(booking, top_theme)`. `top_theme` is already
computed early in `handle()` and threaded into `_finalize_pending_booking`, so
it's available at all 4 sites without new plumbing.

## Testing

Extend the same 4 tests in `src/tests_integration/test_phase3.py` that
currently assert a `"Calendar Hold Creator"` action was queued
(`test_booking_agent_full_flow`, `test_booking_agent_ask_then_book`, and the
reschedule equivalents). For each:

1. Assert a `"Doc Append"` action is queued whose `payload["file_path"] ==
   Config.SHARED_NOTES_PATH` and whose `payload["content"]` contains the
   booking code.
2. Assert an `"Email Draft Generator"` action is queued whose
   `payload["subject"]` (or `topic`) contains the booking code / topic.

Each assertion should also confirm the action type did **not** exist in the
pending queue before the confirming step, mirroring the existing Calendar Hold
assertions.

## Known limitations (out of scope)

- `_queue_doc_append` reads `latest_pulse` / `latest_fee_explainer` directly
  from persistence rather than threading them through as parameters — this
  matches how `_get_top_theme` already reads `latest_pulse` and avoids new
  parameter plumbing.
- No deduplication: a RESCHEDULE queues a fresh Doc Append / Email Draft for
  the new booking, but does not retract the originals queued for the old
  booking. This mirrors the existing Calendar Hold "Known limitation" (stale
  holds aren't retracted either).
