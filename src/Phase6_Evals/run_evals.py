"""
Phase 6: Evals Pipeline — CLI Entry Point

Usage:
    python -m src.Phase6_Evals.run_evals

Runs all 5 evals:
  - Eval 1: Retrieval Accuracy (RAG) — REQUIRED
  - Eval 2: Compliance & Safety (Adversarial) — REQUIRED
  - Eval 3: Tone & Structure (UX) — REQUIRED
  - Eval 4: MCP Approval Gate — Additional
  - Eval 5: Integration / E2E — Additional

Exit code:
  0 — all 3 required evals pass
  1 — one or more required evals fail
"""

import sys
import os
from datetime import datetime

REPORT_PATH = os.path.join(os.path.dirname(__file__), "eval_report.md")


def _section(title: str) -> str:
    return f"\n## {title}\n"


def _table_row(key: str, value: str, status: str) -> str:
    icon = "✅" if status == "PASS" else ("⏭️" if status == "SKIP" else "❌")
    return f"| {key} | {value} | {icon} {status} |"


def generate_report(results: list[dict], run_time_secs: float) -> str:
    """Generate a structured markdown eval report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    required_evals = [r for r in results if r.get("required", False)]
    additional_evals = [r for r in results if not r.get("required", False)]

    all_required_pass = all(r["pass"] for r in required_evals)
    overall_status = "✅ ALL REQUIRED EVALS PASSED" if all_required_pass else "❌ ONE OR MORE REQUIRED EVALS FAILED"

    lines = [
        "# FINTELLIGENCE — Eval Report",
        "",
        f"**Generated:** {timestamp}  ",
        f"**Total runtime:** {run_time_secs:.1f}s  ",
        f"**Overall Status:** {overall_status}",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Eval | Required | Status |",
        "|------|----------|--------|",
    ]

    for r in results:
        req_label = "Required" if r.get("required") else "Additional"
        status = "PASS" if r["pass"] else "FAIL"
        lines.append(_table_row(r["eval_name"], req_label, status))

    lines.append("")
    lines.append("---")

    # Required evals detail
    lines.append(_section("Required Evals"))

    for r in required_evals:
        status_str = "✅ PASS" if r["pass"] else "❌ FAIL"
        lines.append(f"### {r['eval_name']} — {status_str}")
        lines.append("")

        metrics = r.get("metrics", {})
        if metrics:
            lines.append("**Metrics:**")
            for k, v in metrics.items():
                lines.append(f"- `{k}`: {v}")
            lines.append("")

        # Eval-specific details
        if "per_question" in r:
            lines.append("**Per-Question Scores:**")
            lines.append("")
            lines.append("| ID | Question | Faithfulness | Relevance | Citation |")
            lines.append("|----|----------|:------------:|:---------:|:--------:|")
            for q in r["per_question"]:
                cit = "✅" if q["citation_pass"] else "❌"
                lines.append(
                    f"| {q['id']} | {q['question'][:55]}... | {q['faithfulness']} | {q['relevance']} | {cit} |"
                )
            lines.append("")

        if "per_prompt" in r:
            lines.append("**Per-Prompt Results:**")
            lines.append("")
            lines.append("| ID | Prompt | Expected | Refused? | Source |")
            lines.append("|----|--------|----------|:--------:|--------|")
            for p in r["per_prompt"]:
                ref = "✅" if p["refused"] else "❌"
                lines.append(
                    f"| {p['id']} | {p['prompt'][:50]}... | {p['expected']} | {ref} | {p['refusal_source']} |"
                )
            lines.append("")

            if r.get("failures"):
                lines.append("**⚠️ Failures (for fix documentation):**")
                lines.append("")
                for fail in r["failures"]:
                    lines.append(f"- **{fail['prompt_id']}** — Prompt: `{fail['prompt']}`")
                    lines.append(f"  - Guardrail missed: `{fail['guardrail_missed']}`")
                    lines.append(f"  - Detail: {fail['detail']}")
                lines.append("")

        if "checks" in r:
            lines.append("**Structural Checks:**")
            lines.append("")
            lines.append("| Check | Pass | Detail |")
            lines.append("|-------|:----:|--------|")
            for check_name, val in r["checks"].items():
                icon = "✅" if val["pass"] else "❌"
                lines.append(f"| `{check_name}` | {icon} | {val['detail']} |")
            lines.append("")

    # Additional evals detail
    if additional_evals:
        lines.append("---")
        lines.append(_section("Additional Evals"))

        for r in additional_evals:
            status_str = "✅ PASS" if r["pass"] else "❌ FAIL"
            lines.append(f"### {r['eval_name']} — {status_str}")
            lines.append("")

            metrics = r.get("metrics", {})
            if metrics:
                lines.append("**Metrics:**")
                for k, v in metrics.items():
                    lines.append(f"- `{k}`: {v}")
                lines.append("")

            if "checks" in r:
                lines.append("**Checks:**")
                lines.append("")
                lines.append("| Check | Pass | Detail |")
                lines.append("|-------|:----:|--------|")
                for check_name, val in r["checks"].items():
                    icon = "✅" if val["pass"] else "❌"
                    lines.append(f"| `{check_name}` | {icon} | {val['detail']} |")
                lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Report auto-generated by `python -m src.Phase6_Evals.run_evals`*")

    return "\n".join(lines)


def main():
    import time
    import io
    # Force stdout to UTF-8 to handle emoji/special chars on Windows cp1252 terminals
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("=" * 70)
    print("  FINTELLIGENCE - Phase 6 Evals Pipeline")
    print("=" * 70)
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    start = time.time()
    results = []

    # ── Eval 1: RAG Retrieval Accuracy ──────────────────────────────────
    try:
        from src.Phase6_Evals.eval1_rag import run_eval1
        result1 = run_eval1()
    except Exception as e:
        result1 = {
            "eval_name": "Eval 1: Retrieval Accuracy (RAG)",
            "required": True,
            "pass": False,
            "metrics": {"error": str(e)},
        }
        print(f"  [Eval 1] ERROR: {e}")
    results.append(result1)

    # ── Eval 2: Compliance & Safety ─────────────────────────────────────
    try:
        from src.Phase6_Evals.eval2_compliance import run_eval2
        result2 = run_eval2()
    except Exception as e:
        result2 = {
            "eval_name": "Eval 2: Compliance & Safety (Adversarial)",
            "required": True,
            "pass": False,
            "metrics": {"error": str(e)},
        }
        print(f"  [Eval 2] ERROR: {e}")
    results.append(result2)

    # ── Eval 3: Tone & Structure ─────────────────────────────────────────
    try:
        from src.Phase6_Evals.eval3_tone import run_eval3
        result3 = run_eval3()
    except Exception as e:
        result3 = {
            "eval_name": "Eval 3: Tone & Structure (UX)",
            "required": True,
            "pass": False,
            "metrics": {"error": str(e)},
        }
        print(f"  [Eval 3] ERROR: {e}")
    results.append(result3)

    # ── Eval 4: MCP Approval Gate ────────────────────────────────────────
    try:
        from src.Phase6_Evals.eval4_mcp_approval import run_eval4
        result4 = run_eval4()
    except Exception as e:
        result4 = {
            "eval_name": "Eval 4: MCP Approval Gate (Additional)",
            "required": False,
            "pass": False,
            "metrics": {"error": str(e)},
        }
        print(f"  [Eval 4] ERROR: {e}")
    results.append(result4)

    # ── Eval 5: Integration / E2E ────────────────────────────────────────
    try:
        from src.Phase6_Evals.eval5_e2e import run_eval5
        result5 = run_eval5()
    except Exception as e:
        result5 = {
            "eval_name": "Eval 5: Integration / E2E (Additional)",
            "required": False,
            "pass": False,
            "metrics": {"error": str(e)},
        }
        print(f"  [Eval 5] ERROR: {e}")
    results.append(result5)

    run_time = time.time() - start

    # ── Print summary ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    print(f"  {'Eval':<45} {'Required':<12} {'Status'}")
    print("  " + "-" * 65)
    for r in results:
        req = "REQUIRED" if r.get("required") else "additional"
        status = "[PASS]" if r["pass"] else "[FAIL]"
        print(f"  {r['eval_name']:<45} {req:<12} {status}")

    required_results = [r for r in results if r.get("required")]
    all_required_pass = all(r["pass"] for r in required_results)

    print("=" * 70)
    if all_required_pass:
        print("  [OK] ALL 3 REQUIRED EVALS PASSED")
    else:
        failed_required = [r["eval_name"] for r in required_results if not r["pass"]]
        print(f"  [!!] REQUIRED EVALS FAILED: {', '.join(failed_required)}")
    print(f"  Total runtime: {run_time:.1f}s")
    print("=" * 70)

    # ── Generate and save report ─────────────────────────────────────────
    report_md = generate_report(results, run_time)
    try:
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"\n  [REPORT] Saved: {REPORT_PATH}")
    except Exception as e:
        print(f"\n  WARNING: Could not save report: {e}")

    # ── Exit code ────────────────────────────────────────────────────────
    sys.exit(0 if all_required_pass else 1)


if __name__ == "__main__":
    main()
