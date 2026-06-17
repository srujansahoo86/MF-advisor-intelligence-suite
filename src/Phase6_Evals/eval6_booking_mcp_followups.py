"""
Eval 6: Booking Confirmation MCP Follow-ups — Additional Eval

Verifies that confirming a booking via BookingAgent atomically queues exactly
three MCP actions: Calendar Hold Creator, Doc Append, Email Draft Generator.

Tests:
  1. three_actions_queued            — exactly 3 actions PENDING after booking
  2. action_types_correct            — all 3 tool names present
  3. payloads_have_booking_data      — topic + booking code in at least one payload
  4. calendar_hold_approved_executes — approve returns success; calendar_holds persisted
  5. doc_append_approved_executes    — approve returns success; notes file created
  6. email_draft_approved_executes   — approve returns success; latest_email_draft in DB
  7. reject_all_does_not_execute     — reject all 3 from a 2nd booking; nothing executes
"""

import os
import json
from unittest.mock import patch

EVAL6_DB = "./data/eval6_mcp_followups.db"

EXPECTED_TOOL_NAMES = {"Calendar Hold Creator", "Doc Append", "Email Draft Generator"}
MOCK_TOPIC_1 = "Mutual Fund Fees"
MOCK_SLOT_1  = "Monday 10:00 AM"
MOCK_TOPIC_2 = "SIP Planning"
MOCK_SLOT_2  = "Tuesday 10:00 AM"


def run_eval6() -> dict:
    """
    Run Eval 6: Booking Confirmation MCP Follow-ups.
    Returns dict with sub-check results and overall PASS/FAIL.
    """
    from src.Phase3_Voice_Scheduler.booking_agent import BookingAgent
    from src.Phase3_Voice_Scheduler.intent_parser import ParsedIntent
    from src.Phase0_Shared_Foundation.persistence import Persistence
    from src.Phase0_Shared_Foundation.config import Config

    print("\n[Eval 6] Booking Confirmation MCP Follow-ups (Additional)")
    print("=" * 60)

    checks = {}

    # Track whether the shared notes file existed before the eval
    notes_file = Config.SHARED_NOTES_PATH
    notes_existed_before = os.path.exists(notes_file)

    # Clean up any leftover temp DB
    if os.path.exists(EVAL6_DB):
        try:
            os.remove(EVAL6_DB)
        except Exception:
            pass

    try:
        persistence = Persistence(EVAL6_DB)

        # Seed a mock pulse so _queue_doc_append can include a top theme
        persistence.set("latest_pulse", {
            "top_themes": [{"theme_name": "Fee Transparency", "description": "Clients asking about fees."}],
            "user_quotes": ["What is the expense ratio?"],
            "key_observation": "Fee transparency is top of mind.",
            "action_ideas": ["Add fee tooltips.", "Publish fee guide.", "Create fee FAQ."],
            "word_count": 30,
        })

        # ── Happy path: Booking 1 ─────────────────────────────────────
        print("  [6.1-6.3] Confirm booking 1 -> check 3 actions queued with booking data...")

        agent = BookingAgent(db_path=EVAL6_DB)
        mock_parsed = ParsedIntent(intent="BOOK", topic=MOCK_TOPIC_1, slot_preference=MOCK_SLOT_1)

        with patch.object(agent.intent_parser, "parse", return_value=mock_parsed), \
             patch.object(agent.slot_manager, "resolve", return_value=MOCK_SLOT_1):
            resp = agent.handle(f"Book on Monday morning about {MOCK_TOPIC_1}")

        pending = agent.orchestrator.list_pending()
        pending_tools = {a.tool_name for a in pending}
        all_payload_text = " ".join(json.dumps(a.payload) for a in pending)
        booking_code = resp.booking_code or ""

        # Check 1: exactly 3 actions queued
        checks["three_actions_queued"] = {
            "pass": len(pending) == 3,
            "detail": f"pending_count={len(pending)} (expected 3)",
        }

        # Check 2: all 3 correct tool names
        checks["action_types_correct"] = {
            "pass": pending_tools == EXPECTED_TOOL_NAMES,
            "detail": f"tool_names={sorted(pending_tools)}",
        }

        # Check 3: booking data in payloads
        topic_in_payloads = MOCK_TOPIC_1.lower() in all_payload_text.lower()
        code_in_payloads  = bool(booking_code) and booking_code in all_payload_text
        checks["payloads_have_booking_data"] = {
            "pass": topic_in_payloads and code_in_payloads,
            "detail": (
                f"topic_found={topic_in_payloads}, "
                f"code_found={code_in_payloads}, "
                f"booking_code='{booking_code}'"
            ),
        }

        # Map tool name → action_id for targeted approval
        orchestrator = agent.orchestrator
        action_by_tool = {a.tool_name: a.action_id for a in pending}

        # Check 4: approve Calendar Hold → persisted in DB
        print("  [6.4] Approve Calendar Hold...")
        cal_result = orchestrator.approve_action(action_by_tool["Calendar Hold Creator"])
        cal_holds  = persistence.get("calendar_holds") or []
        checks["calendar_hold_approved_executes"] = {
            "pass": cal_result.get("status") == "success" and len(cal_holds) >= 1,
            "detail": (
                f"approve_status={cal_result.get('status')}, "
                f"calendar_holds_count={len(cal_holds)}"
            ),
        }

        # Check 5: approve Doc Append → notes file created
        print("  [6.5] Approve Doc Append...")
        doc_result = orchestrator.approve_action(action_by_tool["Doc Append"])
        notes_created = os.path.exists(notes_file)
        checks["doc_append_approved_executes"] = {
            "pass": doc_result.get("status") == "success" and notes_created,
            "detail": (
                f"approve_status={doc_result.get('status')}, "
                f"notes_file_exists={notes_created} ({notes_file})"
            ),
        }

        # Check 6: approve Email Draft → latest_email_draft persisted
        print("  [6.6] Approve Email Draft...")
        email_result = orchestrator.approve_action(action_by_tool["Email Draft Generator"])
        email_draft  = persistence.get("latest_email_draft")
        checks["email_draft_approved_executes"] = {
            "pass": email_result.get("status") == "success" and bool(email_draft),
            "detail": (
                f"approve_status={email_result.get('status')}, "
                f"email_draft_persisted={bool(email_draft)}"
            ),
        }

        # ── Rejection path: Booking 2 ─────────────────────────────────
        print("  [6.7] Booking 2: reject all 3 -> nothing executes...")

        agent2 = BookingAgent(db_path=EVAL6_DB)
        mock_parsed2 = ParsedIntent(intent="BOOK", topic=MOCK_TOPIC_2, slot_preference=MOCK_SLOT_2)

        with patch.object(agent2.intent_parser, "parse", return_value=mock_parsed2), \
             patch.object(agent2.slot_manager, "resolve", return_value=MOCK_SLOT_2):
            agent2.handle(f"Book on Tuesday morning about {MOCK_TOPIC_2}")

        # Snapshot state before rejecting
        cal_holds_before   = len(persistence.get("calendar_holds") or [])
        email_draft_before = persistence.get("latest_email_draft")

        pending2 = agent2.orchestrator.list_pending()
        for action in pending2:
            agent2.orchestrator.reject_action(action.action_id)

        cal_holds_after   = len(persistence.get("calendar_holds") or [])
        email_draft_after = persistence.get("latest_email_draft")

        reject_ok = (
            len(pending2) == 3 and
            cal_holds_after  == cal_holds_before and
            email_draft_after == email_draft_before
        )
        checks["reject_all_does_not_execute"] = {
            "pass": reject_ok,
            "detail": (
                f"booking2_actions_found={len(pending2)}, "
                f"calendar_holds_unchanged={cal_holds_after == cal_holds_before}, "
                f"email_draft_unchanged={email_draft_after == email_draft_before}"
            ),
        }

    except Exception as e:
        checks["eval6_error"] = {
            "pass": False,
            "detail": f"Unexpected exception: {e}",
        }
    finally:
        # Remove temp DB
        if os.path.exists(EVAL6_DB):
            try:
                os.remove(EVAL6_DB)
            except Exception:
                pass
        # Remove notes file only if the eval created it (wasn't there before)
        if not notes_existed_before and os.path.exists(notes_file):
            try:
                os.remove(notes_file)
            except Exception:
                pass

    total_checks  = len(checks)
    passed_checks = sum(1 for v in checks.values() if v["pass"])
    overall_pass  = all(v["pass"] for v in checks.values())

    for key, val in checks.items():
        icon = "[PASS]" if val["pass"] else "[FAIL]"
        print(f"    {icon} {key}: {val['detail']}")

    return {
        "eval_name": "Eval 6: Booking Confirmation MCP Follow-ups (Additional)",
        "required": False,
        "pass": overall_pass,
        "metrics": {
            "checks_passed": f"{passed_checks}/{total_checks}",
        },
        "checks": checks,
    }
