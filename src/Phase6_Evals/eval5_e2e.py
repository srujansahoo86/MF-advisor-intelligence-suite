"""
Eval 5: Integration / End-to-End Eval — Additional Eval

Full pipeline smoke test:
  CSV → ReviewProcessor → PulseGenerator → top_theme persisted
  → VoiceAdapter reads top_theme → booking greeting mentions it
  → MCPOrchestrator queues email draft
  → Approve → email draft executed and persisted

This tests that the seams between all phases are correctly wired.
Requires GROQ_API_KEY for the PulseGenerator LLM call; if absent, uses a mock pulse.
"""

import os
import re

EVAL5_DB = "./data/eval5_e2e.db"
_BOOKING_CODE_RE = re.compile(r'\bKV-[A-Z0-9]{4}\b')


def run_eval5() -> dict:
    """
    Run Eval 5: Integration E2E.
    Returns dict with sub-check results and overall PASS/FAIL.
    """
    from src.Phase0_Shared_Foundation.persistence import Persistence
    from src.Phase0_Shared_Foundation.config import Config
    from src.Phase3_Voice_Scheduler.voice_adapter import VoiceAdapter
    from src.Phase4_MCP_Orchestration.orchestrator import MCPOrchestrator

    print("\n[Eval 5] Integration / E2E Eval (Additional)")
    print("=" * 60)

    checks = {}

    # Clean up
    for path in [EVAL5_DB, "./data/eval5_email_draft.txt"]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    try:
        persistence = Persistence(EVAL5_DB)

        # ── Step 1: Generate or mock pulse ────────────────────────────
        print("  [5.1] Generate Weekly Pulse (or mock)...")

        has_groq = bool(os.getenv("GROQ_API_KEY"))
        csv_path = Config.REVIEWS_CSV_PATH
        pulse_data = None

        if has_groq and os.path.exists(csv_path):
            try:
                from src.Phase2_Review_Intelligence.review_processor import ReviewProcessor
                from src.Phase2_Review_Intelligence.pulse_generator import PulseGenerator

                processor = ReviewProcessor(csv_path)
                reviews = processor.load()
                gen = PulseGenerator()
                # PulseGenerator writes to its own default DB; we mirror to test DB
                pulse_obj = gen.generate(reviews)
                pulse_data = pulse_obj.model_dump()
            except Exception as e:
                print(f"    WARNING: LLM pulse failed ({e}), using mock pulse.")

        if not pulse_data:
            # Deterministic mock pulse for non-LLM environments
            pulse_data = {
                "top_themes": [
                    {"theme_name": "Direct Plans Conversion", "description": "Many clients asking to switch regular to direct funds."},
                    {"theme_name": "Exit Load Confusion", "description": "Users unaware of exit loads on liquid funds."},
                ],
                "user_quotes": ["How do I switch my regular funds to direct?"],
                "key_observation": "Direct plan conversion and exit load awareness are top concerns.",
                "action_ideas": [
                    "Create one-click regular-to-direct switch.",
                    "Add exit load tooltips in portfolio view.",
                    "Publish infographic on TER differences.",
                ],
                "word_count": 55,
            }

        persistence.set("latest_pulse", pulse_data)
        top_theme = pulse_data["top_themes"][0]["theme_name"]

        checks["pulse_generated_and_persisted"] = {
            "pass": bool(top_theme),
            "detail": f"Top theme: '{top_theme}'",
        }

        # ── Step 2: Voice booking reads top_theme ─────────────────────
        print(f"  [5.2] Voice booking — should mention '{top_theme}' in greeting...")

        adapter = VoiceAdapter(EVAL5_DB)
        voice_result = adapter.process("Book an appointment on Monday morning about mutual fund fees")
        booking_msg = voice_result.message or ""
        booking_code = voice_result.booking_code or ""

        theme_in_greeting = top_theme in booking_msg
        code_valid = bool(_BOOKING_CODE_RE.match(booking_code)) if booking_code else False

        checks["voice_reads_top_theme"] = {
            "pass": theme_in_greeting,
            "detail": f"Theme '{top_theme}' in greeting: {theme_in_greeting}",
        }
        checks["voice_booking_code_generated"] = {
            "pass": code_valid,
            "detail": f"booking_code='{booking_code}' matches KV-XXXX: {code_valid}",
        }

        # ── Step 3: MCP queues email draft, approve → executes ────────
        print("  [5.3] MCP email draft queued and approved...")

        orchestrator = MCPOrchestrator(EVAL5_DB)
        email_payload = {
            "recipient": "advisor@example.com",
            "subject": "Client Inquiry about Mutual Fund Fees",
            "topic": "mutual fund fees and expense ratios",
        }
        action_id = orchestrator.queue_action("Email Draft Generator", email_payload)

        # Assert it's pending (not executed)
        pending = orchestrator.list_pending()
        action_pending = any(a.action_id == action_id for a in pending)

        checks["mcp_email_queued_pending"] = {
            "pass": action_pending,
            "detail": f"action_id={action_id} in pending queue: {action_pending}",
        }

        # Approve and verify execution
        approve_result = orchestrator.approve_action(action_id)
        approve_ok = approve_result.get("status") == "success"

        # Check the email draft was persisted by email_draft_generator
        email_draft = persistence.get("latest_email_draft")
        draft_has_content = bool(email_draft and email_draft.get("body"))

        checks["mcp_email_approved_and_executed"] = {
            "pass": approve_ok and draft_has_content,
            "detail": f"approve_ok={approve_ok}, email_draft_persisted={draft_has_content}",
        }

        # ── Step 4: Pipeline integrity check ─────────────────────────
        # Verify the booking and email reference the same general topic
        print("  [5.4] Pipeline integrity — booking and email connected to topic...")

        email_body = email_draft.get("body", "") if email_draft else ""
        topic_in_email = "mutual fund" in email_body.lower() or "expense" in email_body.lower() or "fee" in email_body.lower()

        checks["pipeline_integrity"] = {
            "pass": topic_in_email,
            "detail": f"Email body references the booking topic: {topic_in_email}",
        }

    except Exception as e:
        checks["eval5_error"] = {
            "pass": False,
            "detail": f"Unexpected exception in Eval 5: {e}",
        }
    finally:
        # Cleanup
        for path in [EVAL5_DB, "./data/eval5_email_draft.txt"]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    total_checks = len(checks)
    passed_checks = sum(1 for v in checks.values() if v["pass"])
    overall_pass = all(v["pass"] for v in checks.values())

    for key, val in checks.items():
        icon = "[PASS]" if val["pass"] else "[FAIL]"
        print(f"    {icon} {key}: {val['detail']}")

    return {
        "eval_name": "Eval 5: Integration / E2E (Additional)",
        "required": False,
        "pass": overall_pass,
        "metrics": {
            "checks_passed": f"{passed_checks}/{total_checks}",
        },
        "checks": checks,
    }
