"""
Eval 4: MCP Approval Eval — Additional Eval

Verifies the core MCP safety property: no action executes without human approval.

Tests:
  1. Queue a tool → assert it lands in PENDING state and does NOT execute
  2. Approve → assert it executes exactly once (side effect is visible)
  3. Reject a separate action → assert it never executes
"""

import os
import tempfile

EVAL4_TEST_FILE = "./data/eval4_mcp_exec_test.txt"
EVAL4_DB = "./data/eval4_mcp.db"


def run_eval4() -> dict:
    """
    Run Eval 4: MCP Approval Gate.
    Returns dict with sub-check results and overall PASS/FAIL.
    """
    from src.Phase4_MCP_Orchestration.orchestrator import MCPOrchestrator

    print("\n[Eval 4] MCP Approval Eval (Additional)")
    print("=" * 60)

    checks = {}

    # Clean up test artifacts
    for path in [EVAL4_TEST_FILE, EVAL4_DB]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    try:
        orchestrator = MCPOrchestrator(EVAL4_DB)

        # ── Test 1: Queue -> PENDING, NOT executed ──────────────────
        print("  [4.1] Queue action: must be PENDING (not executed)...")

        action_id_1 = orchestrator.queue_action("Doc Append", {
            "file_path": EVAL4_TEST_FILE,
            "content": "Approved execution test",
        })

        # The file must NOT exist yet — the tool was not executed
        file_exists_before = os.path.exists(EVAL4_TEST_FILE)
        pending_list = orchestrator.list_pending()
        action_in_queue = any(a.action_id == action_id_1 for a in pending_list)

        checks["queue_is_pending"] = {
            "pass": action_in_queue and not file_exists_before,
            "detail": f"action_id={action_id_1}, in_queue={action_in_queue}, file_exists_before={file_exists_before}",
        }

        # ── Test 2: Approve -> executes exactly once ─────────────────
        print("  [4.2] Approve action: must execute exactly once...")

        result = orchestrator.approve_action(action_id_1)
        file_exists_after = os.path.exists(EVAL4_TEST_FILE)
        approve_success = result.get("status") == "success"

        # Confirm action is no longer pending
        pending_list_after = orchestrator.list_pending()
        not_pending_anymore = not any(a.action_id == action_id_1 for a in pending_list_after)

        checks["approve_executes"] = {
            "pass": approve_success and file_exists_after and not_pending_anymore,
            "detail": f"approve_success={approve_success}, file_created={file_exists_after}, removed_from_queue={not_pending_anymore}",
        }

        # ── Test 3: Reject -> never executes ────────────────────────
        print("  [4.3] Reject action: must never execute...")

        reject_test_file = "./data/eval4_reject_test.txt"
        action_id_2 = orchestrator.queue_action("Doc Append", {
            "file_path": reject_test_file,
            "content": "Should never be written",
        })

        reject_result = orchestrator.reject_action(action_id_2)
        reject_file_exists = os.path.exists(reject_test_file)
        reject_success = reject_result.get("status") == "success"

        checks["reject_does_not_execute"] = {
            "pass": reject_success and not reject_file_exists,
            "detail": f"reject_success={reject_success}, file_should_not_exist={not reject_file_exists}",
        }

        # ── Test 4: Double-approve / double-reject must fail (400 semantics) ──
        print("  [4.4] Re-approving already-resolved action must raise ValueError...")

        double_approve_raises = False
        try:
            orchestrator.approve_action(action_id_1)  # already APPROVED
        except ValueError:
            double_approve_raises = True

        checks["double_approve_raises"] = {
            "pass": double_approve_raises,
            "detail": f"ValueError raised on double-approve: {double_approve_raises}",
        }

    except Exception as e:
        checks["eval4_error"] = {
            "pass": False,
            "detail": f"Unexpected exception in Eval 4: {e}",
        }
    finally:
        # Cleanup
        for path in [EVAL4_TEST_FILE, EVAL4_DB, "./data/eval4_reject_test.txt"]:
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
        "eval_name": "Eval 4: MCP Approval Gate (Additional)",
        "required": False,
        "pass": overall_pass,
        "metrics": {
            "checks_passed": f"{passed_checks}/{total_checks}",
        },
        "checks": checks,
    }
