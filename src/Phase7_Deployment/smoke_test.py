"""
Phase 7 Deployment — Smoke Test
Runs a quick sanity check against the live Render deployment.

Usage:
    python -m src.Phase7_Deployment.smoke_test
    python -m src.Phase7_Deployment.smoke_test --url https://your-app.onrender.com
"""

import sys
import json
import argparse
import urllib.request
import urllib.error

DEFAULT_URL = "https://mf-advisor-intelligence-suite-1.onrender.com"

_results = []


def _check(name, passed, detail=""):
    _results.append((name, passed, detail))
    mark = "PASS" if passed else "FAIL"
    line = f"  [{mark}]  {name}"
    if detail:
        line += f"  —  {detail}"
    print(line)


def _get(base_url, path, timeout=60):
    req = urllib.request.Request(f"{base_url}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


def _post(base_url, path, body, timeout=60):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{base_url}{path}", data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


def run(base_url: str) -> bool:
    base_url = base_url.rstrip("/")
    print(f"\n{'='*62}")
    print(f"  MF Advisor Intelligence Suite — Smoke Test")
    print(f"  Target : {base_url}")
    print(f"{'='*62}\n")

    # 1. Health
    try:
        status, data = _get(base_url, "/health")
        _check(
            "Health check  GET /health",
            status == 200 and data.get("status") == "healthy",
            f"status={data.get('status')}  groq_key_set={data.get('groq_key_set')}"
        )
    except Exception as e:
        _check("Health check  GET /health", False, str(e))

    # 2. FAQ — factual query should return text + at least 1 citation
    try:
        status, data = _post(base_url, "/api/faq",
                             {"query": "What is the exit load for Parag Parikh Liquid Fund?"})
        text = data.get("text", "")
        citations = data.get("citation_links", [])
        _check(
            "FAQ  POST /api/faq",
            status == 200 and len(text) > 10,
            f"answer length={len(text)}  citations={len(citations)}"
        )
    except Exception as e:
        _check("FAQ  POST /api/faq", False, str(e))

    # 3. FAQ guardrail — investment advice must be refused
    try:
        status, data = _post(base_url, "/api/faq",
                             {"query": "Should I buy Parag Parikh Liquid Fund right now?"})
        refused = not data.get("is_safe", True)
        _check(
            "FAQ guardrail  POST /api/faq (advice refusal)",
            status == 200 and refused,
            f"is_safe={data.get('is_safe')}"
        )
    except Exception as e:
        _check("FAQ guardrail  POST /api/faq (advice refusal)", False, str(e))

    # 4. Weekly Pulse
    try:
        status, data = _get(base_url, "/api/pulse")
        _check(
            "Weekly Pulse  GET /api/pulse",
            status == 200 and "top_themes" in data,
            f"themes={len(data.get('top_themes', []))}  quotes={len(data.get('user_quotes', []))}"
        )
    except Exception as e:
        _check("Weekly Pulse  GET /api/pulse", False, str(e))

    # 5. Fee Explainer
    try:
        status, data = _get(base_url, "/api/fee-explainer")
        bullets = data.get("bullets", [])
        _check(
            "Fee Explainer  GET /api/fee-explainer",
            status == 200 and len(bullets) == 6,
            f"bullets={len(bullets)}"
        )
    except Exception as e:
        _check("Fee Explainer  GET /api/fee-explainer", False, str(e))

    # 6. Voice Scheduler
    try:
        status, data = _post(base_url, "/api/voice",
                             {"transcript": "I want to book an appointment"})
        _check(
            "Voice Scheduler  POST /api/voice",
            status == 200 and bool(data.get("message")),
            f"message length={len(data.get('message', ''))}"
        )
    except Exception as e:
        _check("Voice Scheduler  POST /api/voice", False, str(e))

    # 7. MCP Pending Actions
    try:
        status, data = _get(base_url, "/api/actions/pending")
        _check(
            "MCP Approval Queue  GET /api/actions/pending",
            status == 200 and isinstance(data, list),
            f"pending={len(data)}"
        )
    except Exception as e:
        _check("MCP Approval Queue  GET /api/actions/pending", False, str(e))

    # 8. Sources manifest
    try:
        status, data = _get(base_url, "/api/sources")
        sources = data.get("sources", [])
        _check(
            "Sources manifest  GET /api/sources",
            status == 200 and len(sources) >= 30,
            f"source count={len(sources)}"
        )
    except Exception as e:
        _check("Sources manifest  GET /api/sources", False, str(e))

    # Summary
    passed = sum(1 for _, p, _ in _results if p)
    total = len(_results)
    print(f"\n{'='*62}")
    print(f"  Result: {passed}/{total} checks passed  —  "
          f"{'ALL PASS' if passed == total else 'FAILURES DETECTED'}")
    print(f"{'='*62}\n")
    return passed == total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Smoke test for the deployed MF Advisor Intelligence Suite"
    )
    parser.add_argument(
        "--url", default=DEFAULT_URL,
        help=f"Base URL of the deployed app (default: {DEFAULT_URL})"
    )
    args = parser.parse_args()
    ok = run(args.url)
    sys.exit(0 if ok else 1)
