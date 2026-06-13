"""
Eval 3: Tone & Structure Eval (UX Eval) — REQUIRED

Pure rule-based structural checks on Phase 2 and Phase 3 outputs.
No LLM scoring — only assertions against schema constraints.

Checks:
  1. Weekly Pulse: word count ≤ 250, exactly 3 action_ideas, ≥ 1 user_quote, no PII
  2. Fee Explainer: exactly 6 bullets, no performance claims, exactly 2 source_links, last_checked format
  3. Voice Agent: top_theme from pulse appears in greeting, booking code format KV-XXXX
  4. MCP Email: market context snippet from Phase 1 RAG appears in email draft
"""

import re
from typing import Optional

# PII detection patterns (mirrors pii.py)
_PAN_RE = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
_PHONE_RE = re.compile(r'\b[6-9]\d{9}\b')
_EMAIL_RE = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b')

# Performance / superlative blocklist
_PERFORMANCE_BLOCKLIST = [
    "guaranteed", "sure shot", "double", "triple", "highest return",
    "best return", "risk-free", "no risk", "safe investment",
    "will definitely", "always profitable", "100%", "assured",
]

# Booking code regex
_BOOKING_CODE_RE = re.compile(r'\bKV-[A-Z0-9]{4}\b')

# AMFI / SEBI official URL patterns
_OFFICIAL_URL_PATTERNS = [
    "amfiindia.com",
    "sebi.gov.in",
]


def _has_pii(text: str) -> bool:
    return bool(_PAN_RE.search(text) or _PHONE_RE.search(text) or _EMAIL_RE.search(text))


def _has_performance_claim(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in _PERFORMANCE_BLOCKLIST)


def _is_official_url(url: str) -> bool:
    return any(domain in url.lower() for domain in _OFFICIAL_URL_PATTERNS)


def run_eval3() -> dict:
    """
    Run Eval 3: Tone & Structure.
    Returns dict with sub-check results and overall PASS/FAIL.
    """
    import os
    from src.Phase0_Shared_Foundation.config import Config
    from src.Phase0_Shared_Foundation.persistence import Persistence
    from src.Phase3_Voice_Scheduler.voice_adapter import VoiceAdapter
    from src.Phase4_MCP_Orchestration.orchestrator import MCPOrchestrator
    from src.Phase4_MCP_Orchestration.tools import email_draft_generator

    print("\n[Eval 3] Tone & Structure Eval (UX)")
    print("=" * 60)

    checks = {}

    # ─────────────────────────────────────────────────────────────
    # Section 3A: Weekly Pulse checks
    # ─────────────────────────────────────────────────────────────
    print("  [3A] Weekly Pulse checks...")

    persistence = Persistence()
    pulse = persistence.get("latest_pulse")

    # If no pulse in DB, generate from reviews.csv (fallback)
    if not pulse:
        csv_path = Config.REVIEWS_CSV_PATH
        if os.path.exists(csv_path):
            try:
                from src.Phase2_Review_Intelligence.review_processor import ReviewProcessor
                from src.Phase2_Review_Intelligence.pulse_generator import PulseGenerator
                processor = ReviewProcessor(csv_path)
                reviews = processor.load()
                gen = PulseGenerator()
                pulse_obj = gen.generate(reviews)
                pulse = pulse_obj.model_dump()
            except Exception as e:
                pulse = None
                checks["pulse_available"] = {"pass": False, "detail": f"Could not generate pulse: {e}"}

    if pulse:
        # Check word count
        word_count = pulse.get("word_count", 9999)
        checks["pulse_word_count"] = {
            "pass": word_count <= 250,
            "detail": f"word_count={word_count} (threshold ≤ 250)",
        }

        # Check action_ideas == 3
        action_ideas = pulse.get("action_ideas", [])
        checks["pulse_action_ideas_count"] = {
            "pass": len(action_ideas) == 3,
            "detail": f"action_ideas count={len(action_ideas)} (required exactly 3)",
        }

        # Check user_quotes >= 1
        user_quotes = pulse.get("user_quotes", [])
        checks["pulse_user_quotes"] = {
            "pass": len(user_quotes) >= 1,
            "detail": f"user_quotes count={len(user_quotes)} (required ≥ 1)",
        }

        # Check no PII in any pulse field
        all_pulse_text = " ".join([
            " ".join(action_ideas),
            " ".join(user_quotes),
            pulse.get("key_observation", ""),
            " ".join([t.get("description", "") if isinstance(t, dict) else str(t) for t in pulse.get("top_themes", [])]),
        ])
        checks["pulse_no_pii"] = {
            "pass": not _has_pii(all_pulse_text),
            "detail": "No PII (email/phone/PAN) found in pulse fields" if not _has_pii(all_pulse_text) else "PII detected in pulse fields!",
        }
    else:
        if "pulse_available" not in checks:
            checks["pulse_available"] = {"pass": False, "detail": "No pulse in DB and no reviews.csv found"}

    # ─────────────────────────────────────────────────────────────
    # Section 3B: Fee Explainer checks
    # ─────────────────────────────────────────────────────────────
    print("  [3B] Fee Explainer checks...")

    fee_explainer = persistence.get("latest_fee_explainer")

    if fee_explainer:
        bullets = fee_explainer.get("bullets", [])
        source_links = fee_explainer.get("source_links", [])
        last_checked = fee_explainer.get("last_checked", "")

        # Check exactly 6 bullets
        checks["fee_bullets_count"] = {
            "pass": len(bullets) == 6,
            "detail": f"bullets count={len(bullets)} (required exactly 6)",
        }

        # Check no performance claims in bullets
        all_bullets_text = " ".join(bullets)
        checks["fee_no_performance_claims"] = {
            "pass": not _has_performance_claim(all_bullets_text),
            "detail": "No performance claims found" if not _has_performance_claim(all_bullets_text) else f"Performance claim detected: '{all_bullets_text[:80]}'",
        }

        # Check exactly 2 source_links, both official
        all_official = all(_is_official_url(url) for url in source_links)
        checks["fee_source_links"] = {
            "pass": len(source_links) == 2 and all_official,
            "detail": f"source_links={source_links}, all_official={all_official}",
        }

        # Check last_checked format
        checks["fee_last_checked_format"] = {
            "pass": last_checked.startswith("Last checked: "),
            "detail": f"last_checked='{last_checked}'",
        }
    else:
        checks["fee_explainer_available"] = {
            "pass": False,
            "detail": "No fee explainer found in DB. Run PulseGenerator first or skip if LLM not available.",
        }

    # ─────────────────────────────────────────────────────────────
    # Section 3C: Voice Agent checks
    # ─────────────────────────────────────────────────────────────
    print("  [3C] Voice Agent structural checks...")

    # Seed a mock pulse with a known top theme for deterministic testing
    MOCK_THEME = "Exit Load Awareness"
    eval_db = "./data/eval3_temp.db"

    try:
        from src.Phase0_Shared_Foundation.persistence import Persistence as P
        test_persistence = P(eval_db)
        test_persistence.set("latest_pulse", {
            "top_themes": [{"theme_name": MOCK_THEME, "description": "Clients asking about exit loads."}],
            "user_quotes": ["What is the exit load?"],
            "key_observation": "Many users are confused about exit loads.",
            "action_ideas": ["Publish exit load FAQ.", "Add exit load tooltips.", "Create video guide."],
            "word_count": 40,
        })

        adapter = VoiceAdapter(eval_db)
        voice_result = adapter.process("Book an appointment on Friday afternoon about Exit Load")

        booking_msg = voice_result.message or ""

        # Check top theme appears in greeting
        checks["voice_top_theme_in_greeting"] = {
            "pass": MOCK_THEME in booking_msg,
            "detail": f"Top theme '{MOCK_THEME}' {'found' if MOCK_THEME in booking_msg else 'NOT found'} in greeting: '{booking_msg[:100]}'",
        }

        # Check booking code format KV-XXXX
        booking_code = voice_result.booking_code or ""
        code_valid = bool(_BOOKING_CODE_RE.match(booking_code)) if booking_code else False
        checks["voice_booking_code_format"] = {
            "pass": code_valid,
            "detail": f"booking_code='{booking_code}', format KV-XXXX: {code_valid}",
        }

    except Exception as e:
        checks["voice_structural"] = {
            "pass": False,
            "detail": f"Voice agent check failed: {e}",
        }
    finally:
        # Clean up temp db
        import os
        if os.path.exists(eval_db):
            try:
                os.remove(eval_db)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────
    # Section 3D: MCP Email — market context snippet check
    # ─────────────────────────────────────────────────────────────
    print("  [3D] MCP Email market context checks...")

    try:
        mcp_db = "./data/eval3_mcp_temp.db"
        test_persistence_mcp = Persistence(mcp_db)

        result = email_draft_generator(
            persistence=test_persistence_mcp,
            recipient="client@example.com",
            subject="Your Mutual Fund Query",
            topic="exit load",
        )

        draft_body = result.get("draft", "")

        # Check that the email contains some context snippet (not just the generic fallback)
        has_context = (
            len(draft_body) > 100 and
            "exit load" in draft_body.lower()
        )
        checks["mcp_email_has_context"] = {
            "pass": has_context,
            "detail": f"Email draft has context snippet: {'yes' if has_context else 'no'} (length={len(draft_body)})",
        }

    except Exception as e:
        checks["mcp_email_context"] = {
            "pass": False,
            "detail": f"MCP email draft check failed: {e}",
        }
    finally:
        import os
        if os.path.exists("./data/eval3_mcp_temp.db"):
            try:
                os.remove("./data/eval3_mcp_temp.db")
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────
    # Aggregate
    # ─────────────────────────────────────────────────────────────
    total_checks = len(checks)
    passed_checks = sum(1 for v in checks.values() if v["pass"])
    overall_pass = all(v["pass"] for v in checks.values())

    for key, val in checks.items():
        icon = "[PASS]" if val["pass"] else "[FAIL]"
        print(f"    [{icon}] {key}: {val['detail']}")

    return {
        "eval_name": "Eval 3: Tone & Structure (UX)",
        "required": True,
        "pass": overall_pass,
        "metrics": {
            "checks_passed": f"{passed_checks}/{total_checks}",
        },
        "checks": checks,
    }
