# Eval 6: Booking Confirmation MCP Follow-ups — Design Spec

**Date:** 2026-06-18  
**Phase:** Phase 6 Evals  
**Status:** Approved

---

## Background

Commits on 2026-06-14 added `_queue_mcp_followups` to `BookingAgent`. On every confirmed booking or reschedule, the method atomically queues three MCP actions:

1. **Calendar Hold Creator** — blocks the advisor's calendar for the slot
2. **Doc Append** — logs the booking details to a shared notes file
3. **Email Draft Generator** — drafts a pre-meeting brief for the advisor

These actions were not covered by the existing eval suite (last run: 2026-06-13). Eval 6 fills that gap.

---

## Scope

Eval 6 is a **focused lifecycle eval** for the booking-confirmation → MCP follow-up path. It does not re-test the voice layer (Eval 5 owns that seam) or the general MCP approval gate (Eval 4 owns that).

**In scope:**
- Exactly 3 actions queued after a confirmed booking
- Correct tool names and booking-specific payloads
- Approve-all path: all 3 execute correctly
- Reject-all path: none execute

**Out of scope:**
- STT/TTS stack
- RAG retrieval
- Compliance/safety guardrails
- Partial approval (2 of 3) — not a defined use case

---

## Architecture

**Layer under test:** `BookingAgent` (not `VoiceAdapter`)

`BookingAgent` is the layer that calls `_queue_mcp_followups`. Testing at this seam:
- Keeps the eval fast and deterministic (zero LLM calls)
- Avoids duplicating VoiceAdapter coverage that Eval 5 already provides
- Directly exercises the code path that changed

**Test DB:** Isolated temp SQLite at `./data/eval6_mcp_followups.db`, deleted after.

**Slot seeding:** A known available slot is pre-seeded so the booking auto-confirms in a single `BookingAgent.process()` call — no second utterance needed.

**Pulse seeding:** A minimal mock pulse with a known `top_theme` is written so `_queue_doc_append` can include it in the payload.

---

## Checks (7 total)

### Happy path — Booking 1

| ID | Check | Pass condition |
|----|-------|----------------|
| 1 | `three_actions_queued` | `len(pending_queue) == 3` immediately after booking confirms |
| 2 | `action_types_correct` | Queue contains exactly: `Calendar Hold Creator`, `Doc Append`, `Email Draft Generator` |
| 3 | `payloads_have_booking_data` | Booking topic and booking code (`KV-XXXX`) appear in at least one action payload |
| 4 | `calendar_hold_approved_executes` | `approve_action(calendar_id)` returns `status=success`; calendar hold persisted to DB |
| 5 | `doc_append_approved_executes` | `approve_action(doc_id)` returns `status=success`; output file created |
| 6 | `email_draft_approved_executes` | `approve_action(email_id)` returns `status=success`; `latest_email_draft` key present in DB |

### Rejection path — Booking 2

| ID | Check | Pass condition |
|----|-------|----------------|
| 7 | `reject_all_does_not_execute` | After `reject_action` on all 3 actions from a second booking: no new file, no calendar hold, no email draft written |

---

## Pass/Fail Threshold

All 7 checks must pass for Eval 6 to pass. Any single failure is a blocker.

---

## Integration into run_evals.py

- Added as **Eval 6** after the existing Eval 5 block
- `required: False` — classified as an **additional eval** (same tier as Evals 4 and 5)
- Exit code behavior unchanged: only required evals (1–3) gate the exit code
- Report section added under "Additional Evals"

---

## File layout

```
src/Phase6_Evals/
├── eval6_booking_mcp_followups.py   ← new file
└── run_evals.py                     ← add Eval 6 block
```

---

## Cleanup

Eval 6 cleans up after itself regardless of pass/fail:
- Deletes `./data/eval6_mcp_followups.db`
- Deletes any output file created by Doc Append during the approve test
- Runs in a `try/finally` block
