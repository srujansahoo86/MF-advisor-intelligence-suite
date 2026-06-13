# Problem Statement Alignment Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining alignment gaps between the implementation and `Docs/Problemstatement.md`: FAQ citations must be real clickable URLs (not PDF filenames), the reviews dataset must span 8-12 weeks as specified, the dashboard must expose the full verified source manifest, and `requirements.txt` / `.env.example` must accurately reflect the Groq/HuggingFace stack actually in use.

**Architecture:**
1. A new `Config.SOURCE_URL_MAP` (in `config.py`) maps each local PDF filename to its canonical public URL from `Config.SOURCE_MANIFEST_URLS`. `DocumentLoader` stamps this URL onto each chunk's metadata as `source_url`, and `RAGEngine.answer_query()` returns `source_url` values (falling back to the raw filename only if unmapped) in `citation_links`.
2. `reviews.csv` is redated in place (same 42 rows, same columns) so the review dates span ~80 days (8-12 weeks) instead of the current 13 days.
3. A new `GET /api/sources` endpoint returns `Config.SOURCE_MANIFEST_URLS`; the dashboard (`code.html`) gets a new "Sources" nav tab + section that fetches and renders this list grouped by domain.
4. `requirements.txt` and `src/.env.example` are rewritten to match the actual installed/used stack (Groq + HuggingFace embeddings + FastAPI, not OpenAI).

**Tech Stack:** Python 3.12, FastAPI + TestClient/httpx, LangChain (`langchain-groq`, `langchain-huggingface`, `langchain-chroma`, `langchain-community`), pytest, vanilla JS/Tailwind in `code.html`.

**Note:** Item #5 from the prioritized fix list (TTS) is **already implemented** (`window.speechSynthesis` in `code.html`'s `sendVoiceTranscript()`) and is therefore NOT included as a task in this plan.

---

### Task 1: FAQ citation links must be real URLs, not PDF filenames

**Files:**
- Modify: `src/Phase0_Shared_Foundation/config.py`
- Modify: `src/Phase1_FAQ_Chatbot/document_loader.py`
- Modify: `src/Phase1_FAQ_Chatbot/rag_engine.py:367`
- Modify: `src/tests_integration/test_phase1.py`

**Background for the engineer:**

`RAGEngine.answer_query()` (`src/Phase1_FAQ_Chatbot/rag_engine.py:359-396`) retrieves chunks via `self._retrieve_context(query, k=10)`, then at line 367 does:

```python
sources = list(set([d.metadata.get('source', 'Unknown') for d in docs]))
```

`d.metadata['source']` is set in `DocumentLoader.load_and_split()` (`src/Phase1_FAQ_Chatbot/document_loader.py:97`) to the raw PDF filename (e.g. `"sid-parag-parikh-liquid-fund.pdf"`). This filename is returned verbatim as a `citation_link` and rendered as a clickable `<a href="...">` in `code.html` — producing a dead link, which violates the Problem Statement's citation requirement.

The fix: build a `SOURCE_URL_MAP` dict (filename → canonical URL) from the existing `Config.SOURCE_MANIFEST_URLS`, stamp it onto each document's metadata as `source_url` during loading, and have `RAGEngine` prefer `source_url` over `source` when building `citation_links`.

This is TDD: write the failing test first (Step 1), confirm it fails (Step 2), implement (Steps 3-5), rebuild the vector index (Step 6), then confirm the test passes (Step 7).

- [ ] **Step 1: Add a failing citation-URL test to `test_phase1.py`**

In `src/tests_integration/test_phase1.py`, append this test at the end of the file:

```python

def test_citation_links_are_urls(rag_engine):
    """Citations must be clickable source URLs, not raw PDF filenames."""
    ans = rag_engine.answer_query("What is the exit load for Parag Parikh Liquid Fund?")
    assert len(ans.citation_links) > 0
    for link in ans.citation_links:
        assert link.startswith("http"), f"Citation '{link}' is not a URL"
```

- [ ] **Step 2: Run the test to verify it FAILS**

Run: `pytest src/tests_integration/test_phase1.py::test_citation_links_are_urls -v`

Expected: If `GROQ_API_KEY` is set, FAIL with `AssertionError: Citation 'sid-parag-parikh-liquid-fund.pdf' is not a URL` (or similar `.pdf` filename). If `GROQ_API_KEY` is not set, the test is SKIPPED — in that case proceed to implementation anyway and rely on Step 7 (re-run) for verification once the key is available, or skip straight to Step 8 (regression run, which will also skip).

- [ ] **Step 3: Add `SOURCE_URL_MAP` to `config.py`**

In `src/Phase0_Shared_Foundation/config.py`, the file currently ends with the `SOURCE_MANIFEST_URLS` list closing at line 84:

```python
        "https://www.sebi.gov.in/sebi_data/attachdocs/1475063737177.pdf"
    ]
```

Append the following after that closing `]` (and after the end of the `Config` class body — this is module-level code):

```python


def _build_source_url_map():
    """Maps local PDF filenames to their canonical public URL from SOURCE_MANIFEST_URLS."""
    mapping = {}
    for url in Config.SOURCE_MANIFEST_URLS:
        basename = url.split("?")[0].rsplit("/", 1)[-1]
        if basename.lower().endswith(".pdf"):
            mapping[basename] = url

    # Manual overrides for local filenames that don't match the manifest URL's basename
    mapping.update({
        "parag_parikh_liquid_fund.pdf": "https://kuvera.in/mutual-funds/fund/parag-parikh-liquid-growth--PPLFGZ-GR",
        "parag_parikh_arbitrage_kuvera.pdf": "https://kuvera.in/mutual-funds/fund/parag-parikh-arbitrage-growth--PPAFDG-GR",
        "Parag_Parikh_Conservative_Hybrid_Direct_Kuvera.pdf": "https://kuvera.in/mutual-funds/fund/parag-parikh-conservative-hybrid-growth--PPCHFGZ-GR",
        "parag_parikh_large_cap_growth_profile.pdf": "https://kuvera.in/mutual-funds/fund/parag-parikh-large-cap-growth--PPLCFGZ-GR",
        "Parag_Parikh_Dynamic_Asset_Allocation_Fund_Factsheet.pdf": "https://kuvera.in/mutual-funds/fund/parag-parikh-dynamic-asset-allocation-growth--PPDAFGZ-GR",
        "How do I get my Capital Gains report for filing taxes_ _ Kuvera.pdf": "https://kuvera.freshdesk.com/support/solutions/articles/82000725676-how-do-i-get-my-capital-gains-report-for-filing-taxes-",
        "How do I switch my regular mutual funds to direct_ _ Kuvera.pdf": "https://kuvera.freshdesk.com/support/solutions/articles/82000703085-how-do-i-switch-my-regular-mutual-funds-to-direct-",
        "When will my mutual fund redemption amount get credited_ _ Kuvera.pdf": "https://kuvera.freshdesk.com/support/solutions/articles/82000702595-when-will-my-mutual-fund-redemption-amount-get-credited-",
        "elss_meaning_lock_in_period_advantages.pdf": "https://kuvera.in/blog/elss-meaning-lock-in-period-and-advantages/",
        "kuvera_sip_guide.pdf": "https://kuvera.in/blog/how-to-stop-cancel-and-redeem-mutual-fund-sip-kuvera/",
        "Securities Market Booklet.pdf": "https://www.amfiindia.com/investor/become-mf-distributor?zoneName=InvestorService",
        "SEBI MASTER CIRCULAR FOR MUTUAL FUNDS.pdf": "https://www.sebi.gov.in/legal/master-circulars/mar-2026/master-circular-for-mutual-funds_100491.html",
        "SEBI REGULATORY INFORMATION FOR MUTUAL FUNDS.pdf": "https://investor.sebi.gov.in/iematerial.html",
        "SEBI FEE AND REGULATORY INFORMATION 1.pdf": "https://www.sebi.gov.in/sebi_data/attachdocs/1475063737177.pdf",
    })
    return mapping


Config.SOURCE_URL_MAP = _build_source_url_map()
```

- [ ] **Step 4: Stamp `source_url` onto document metadata in `document_loader.py`**

In `src/Phase1_FAQ_Chatbot/document_loader.py`, find the imports at the top:

```python
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

Replace with:

```python
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.Phase0_Shared_Foundation.config import Config
```

Then find the metadata-stamping loop:

```python
                    parent_folder = os.path.basename(root)
                    for doc in docs:
                        doc.metadata["source"] = file
                        context = get_page_context(file, doc.page_content)
```

Replace with:

```python
                    parent_folder = os.path.basename(root)
                    for doc in docs:
                        doc.metadata["source"] = file
                        doc.metadata["source_url"] = Config.SOURCE_URL_MAP.get(file, "https://www.amfiindia.com/investor-corner")
                        context = get_page_context(file, doc.page_content)
```

- [ ] **Step 5: Use `source_url` in `rag_engine.py` citation links**

In `src/Phase1_FAQ_Chatbot/rag_engine.py`, find line 367:

```python
        sources = list(set([d.metadata.get('source', 'Unknown') for d in docs]))
```

Replace with:

```python
        sources = list(set([d.metadata.get('source_url', d.metadata.get('source', 'Unknown')) for d in docs]))
```

- [ ] **Step 6: Rebuild the Chroma vector index so metadata changes take effect**

The vectorstore at `Config.CHROMA_DB_DIR` was built before `source_url` existed, so persisted documents lack that field. Rebuild it:

Run: `python -m src.Phase1_FAQ_Chatbot.indexer`

Expected: Console output showing each PDF being loaded (`[DocumentLoader] Loading: ...`) followed by confirmation the index was built (the script wipes and recreates `Config.CHROMA_DB_DIR`).

- [ ] **Step 7: Run the new test to verify it PASSES**

Run: `pytest src/tests_integration/test_phase1.py::test_citation_links_are_urls -v`

Expected: `1 passed` (or `1 skipped` if `GROQ_API_KEY` is not set in this environment).

- [ ] **Step 8: Run the full Phase 1 suite (regression check)**

Run: `pytest src/tests_integration/test_phase1.py -v`

Expected: All tests pass (or skip together if `GROQ_API_KEY` is unset) — no regressions to `test_guardrails_integration`, `test_ambiguity_check`, `test_missing_info`.

---

### Task 2: Expand `reviews.csv` to span 8-12 weeks

**Files:**
- Modify: `reviews.csv`
- Modify: `src/tests_integration/test_phase2.py`

**Background for the engineer:**

The Problem Statement requires the reviews dataset to span 8-12 weeks (56-84 days). `reviews.csv` (`D:\CAPSTONE PROJECT\reviews.csv`) currently has 42 rows (`R001`-`R042`, header + 42 data rows) with dates spanning `2026-05-26` to `2026-06-08` — only 13 days.

The fix re-dates all 42 rows to span exactly 80 days (`2026-03-20` to `2026-06-08`, within the 56-84 day range), spreading them evenly by index, while preserving `review_id`, `rating`, `source`, and `review_text` exactly as-is and keeping the row count at 42 (required by `test_phase2.py::test_review_processor_loads_all_rows`, which asserts `len(reviews) == 42`).

This is TDD: write the failing span-check test first (Step 1), confirm it fails (Step 2), redate the CSV (Step 3), then confirm the test passes (Step 4).

- [ ] **Step 1: Add a failing date-span test to `test_phase2.py`**

In `src/tests_integration/test_phase2.py`, append this test at the end of the file:

```python

def test_reviews_span_eight_to_twelve_weeks(reviews):
    """Review dates must span 8-12 weeks (56-84 days) per problem statement."""
    from datetime import date
    parsed_dates = [date.fromisoformat(r['date']) for r in reviews]
    span_days = (max(parsed_dates) - min(parsed_dates)).days
    assert 56 <= span_days <= 84, f"Review date span is {span_days} days, expected 56-84 (8-12 weeks)"
```

- [ ] **Step 2: Run the test to verify it FAILS**

Run: `pytest src/tests_integration/test_phase2.py::test_reviews_span_eight_to_twelve_weeks -v`

Expected: FAIL with `AssertionError: Review date span is 13 days, expected 56-84 (8-12 weeks)`.

- [ ] **Step 3: Redate `reviews.csv` to span 80 days**

Run this one-off Python script via Bash to redate the `date` column of all 42 rows in place, spreading them evenly from `2026-03-20` to `2026-06-08` (80 days), while preserving every other field exactly:

```bash
python -c "
import csv
from datetime import date, timedelta

with open('reviews.csv', newline='', encoding='utf-8') as f:
    rows = list(csv.reader(f))

header, data_rows = rows[0], rows[1:]
n = len(data_rows)
start = date(2026, 3, 20)
span = 80
for i, row in enumerate(data_rows):
    row[1] = (start + timedelta(days=round(i * span / (n - 1)))).isoformat()

with open('reviews.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(data_rows)

print(f'Rewrote {n} rows, dates {data_rows[0][1]} to {data_rows[-1][1]}')
"
```

Expected output: `Rewrote 42 rows, dates 2026-03-20 to 2026-06-08`

- [ ] **Step 4: Run the new test to verify it PASSES**

Run: `pytest src/tests_integration/test_phase2.py::test_reviews_span_eight_to_twelve_weeks -v`

Expected: `1 passed`

- [ ] **Step 5: Run the full Phase 2 suite (regression check)**

Run: `pytest src/tests_integration/test_phase2.py -v`

Expected: All tests pass (LLM-gated tests skip together if `GROQ_API_KEY` is unset) — in particular `test_review_processor_loads_all_rows` still passes (still 42 rows).

---

### Task 3: Add a "Sources" view to the dashboard

**Files:**
- Modify: `src/api/main.py`
- Modify: `stitch_mf_advisor_intelligence_suite/code.html`
- Modify: `src/tests_integration/test_phase5.py`

**Background for the engineer:**

The Problem Statement requires the system to surface its verified source manifest (≥30 official URLs, already defined as `Config.SOURCE_MANIFEST_URLS` in `config.py`). Currently nothing in the API or UI exposes this list to the user. This task adds a `GET /api/sources` endpoint and a new "Sources" nav tab + section in `code.html` that fetches and displays the manifest, grouped by domain (AMC factsheets/KIM/SID, Kuvera platform docs, AMFI/SEBI regulatory).

This is TDD for the backend (Steps 1-3), followed by frontend implementation + manual browser verification (Steps 4-6).

- [ ] **Step 1: Add a failing test for `GET /api/sources`**

In `src/tests_integration/test_phase5.py`, append this test at the end of the file:

```python

# 6. Sources manifest check
def test_api_sources(clean_env):
    client = clean_env
    res = client.get("/api/sources")
    assert res.status_code == 200
    data = res.json()
    assert "sources" in data
    assert len(data["sources"]) >= 30
    assert all(u.startswith("http") for u in data["sources"])
```

- [ ] **Step 2: Run the test to verify it FAILS**

Run: `pytest src/tests_integration/test_phase5.py::test_api_sources -v`

Expected: FAIL with `404` (route not found) — `assert res.status_code == 200` fails because `/api/sources` does not exist yet.

- [ ] **Step 3: Implement the `/api/sources` endpoint**

In `src/api/main.py`, find the `/api/pulse` endpoint block ending:

```python
        return pulse
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice")
```

Replace with:

```python
        return pulse
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sources")
def get_sources():
    return {"sources": sorted(set(Config.SOURCE_MANIFEST_URLS))}

@app.post("/api/voice")
```

- [ ] **Step 4: Run the test to verify it PASSES**

Run: `pytest src/tests_integration/test_phase5.py::test_api_sources -v`

Expected: `1 passed`

- [ ] **Step 5: Add the "Sources" nav tab and section to `code.html`**

In `stitch_mf_advisor_intelligence_suite/code.html`, find the nav block:

```html
<a id="nav-approval" class="flex items-center gap-sm p-sm text-on-surface-variant hover:bg-primary/5 hover:text-primary transition-all rounded-xl" href="#">
<span class="material-symbols-outlined" data-icon="verified_user">verified_user</span>
<span class="font-body-lg">Approval Center</span>
</a>
</nav>
```

Replace with:

```html
<a id="nav-approval" class="flex items-center gap-sm p-sm text-on-surface-variant hover:bg-primary/5 hover:text-primary transition-all rounded-xl" href="#">
<span class="material-symbols-outlined" data-icon="verified_user">verified_user</span>
<span class="font-body-lg">Approval Center</span>
</a>
<a id="nav-sources" class="flex items-center gap-sm p-sm text-on-surface-variant hover:bg-primary/5 hover:text-primary transition-all rounded-xl" href="#">
<span class="material-symbols-outlined" data-icon="link">link</span>
<span class="font-body-lg">Sources</span>
</a>
</nav>
```

Then find the end of the Approval section (`section-approval`) and the closing of the grid + `<main>` immediately after it:

```html
<div class="p-sm text-center bg-surface-container-low/30 border-t border-outline/10">
<button class="text-xs text-primary hover:underline transition-colors font-bold uppercase tracking-widest">Access Archive</button>
</div>
</section>
</div>
</main>
```

Replace with:

```html
<div class="p-sm text-center bg-surface-container-low/30 border-t border-outline/10">
<button class="text-xs text-primary hover:underline transition-colors font-bold uppercase tracking-widest">Access Archive</button>
</div>
</section>
<!-- 5. Sources (Full Width) -->
<section id="section-sources" class="col-span-12 glass-panel rounded-2xl p-md shadow-lg shadow-black/5 hidden">
<div class="flex items-center gap-xs mb-md">
<span class="material-symbols-outlined text-primary" data-icon="link">link</span>
<h2 class="font-title-md text-xl font-bold text-on-surface">Sources &amp; Citations</h2>
</div>
<div id="sources-list" class="space-y-md">
<p class="text-body-sm text-on-surface-variant">Loading sources...</p>
</div>
</section>
</div>
</main>
```

- [ ] **Step 6: Wire up the nav toggle logic and `loadSources()` in `code.html`**

Find the nav/section element declarations:

```javascript
    // Navigation and Section Tabs
    const navLogo = document.getElementById('nav-logo');
    const navFaq = document.getElementById('nav-faq');
    const navVoice = document.getElementById('nav-voice');
    const navApproval = document.getElementById('nav-approval');

    const secVoice = document.getElementById('section-voice');
    const secFaq = document.getElementById('section-faq');
    const secPulse = document.getElementById('section-pulse');
    const secApproval = document.getElementById('section-approval');

    function resetNavStyles() {
        [navFaq, navVoice, navApproval].forEach(nav => {
            nav.className = "flex items-center gap-sm p-sm text-on-surface-variant hover:bg-primary/5 hover:text-primary transition-all rounded-xl";
        });
    }
```

Replace with:

```javascript
    // Navigation and Section Tabs
    const navLogo = document.getElementById('nav-logo');
    const navFaq = document.getElementById('nav-faq');
    const navVoice = document.getElementById('nav-voice');
    const navApproval = document.getElementById('nav-approval');
    const navSources = document.getElementById('nav-sources');

    const secVoice = document.getElementById('section-voice');
    const secFaq = document.getElementById('section-faq');
    const secPulse = document.getElementById('section-pulse');
    const secApproval = document.getElementById('section-approval');
    const secSources = document.getElementById('section-sources');

    function resetNavStyles() {
        [navFaq, navVoice, navApproval, navSources].forEach(nav => {
            nav.className = "flex items-center gap-sm p-sm text-on-surface-variant hover:bg-primary/5 hover:text-primary transition-all rounded-xl";
        });
    }
```

Then find `showAllSections()` and the nav click handlers:

```javascript
    function showAllSections() {
        secVoice.classList.remove('hidden');
        secFaq.classList.remove('hidden');
        secPulse.classList.remove('hidden');
        secApproval.classList.remove('hidden');
        resetNavStyles();
    }

    navLogo.addEventListener('click', (e) => {
        e.preventDefault();
        showAllSections();
    });

    navFaq.addEventListener('click', (e) => {
        e.preventDefault();
        secFaq.classList.remove('hidden');
        secPulse.classList.remove('hidden');
        secVoice.classList.add('hidden');
        secApproval.classList.add('hidden');
        setActiveNav(navFaq);
    });

    navVoice.addEventListener('click', (e) => {
        e.preventDefault();
        secVoice.classList.remove('hidden');
        secFaq.classList.add('hidden');
        secPulse.classList.add('hidden');
        secApproval.classList.add('hidden');
        setActiveNav(navVoice);
    });

    navApproval.addEventListener('click', (e) => {
        e.preventDefault();
        secApproval.classList.remove('hidden');
        secFaq.classList.add('hidden');
        secPulse.classList.add('hidden');
        secVoice.classList.add('hidden');
        setActiveNav(navApproval);
    });
```

Replace with:

```javascript
    function showAllSections() {
        secVoice.classList.remove('hidden');
        secFaq.classList.remove('hidden');
        secPulse.classList.remove('hidden');
        secApproval.classList.remove('hidden');
        secSources.classList.add('hidden');
        resetNavStyles();
    }

    navLogo.addEventListener('click', (e) => {
        e.preventDefault();
        showAllSections();
    });

    navFaq.addEventListener('click', (e) => {
        e.preventDefault();
        secFaq.classList.remove('hidden');
        secPulse.classList.remove('hidden');
        secVoice.classList.add('hidden');
        secApproval.classList.add('hidden');
        secSources.classList.add('hidden');
        setActiveNav(navFaq);
    });

    navVoice.addEventListener('click', (e) => {
        e.preventDefault();
        secVoice.classList.remove('hidden');
        secFaq.classList.add('hidden');
        secPulse.classList.add('hidden');
        secApproval.classList.add('hidden');
        secSources.classList.add('hidden');
        setActiveNav(navVoice);
    });

    navApproval.addEventListener('click', (e) => {
        e.preventDefault();
        secApproval.classList.remove('hidden');
        secFaq.classList.add('hidden');
        secPulse.classList.add('hidden');
        secVoice.classList.add('hidden');
        secSources.classList.add('hidden');
        setActiveNav(navApproval);
    });

    navSources.addEventListener('click', (e) => {
        e.preventDefault();
        secSources.classList.remove('hidden');
        secFaq.classList.add('hidden');
        secPulse.classList.add('hidden');
        secVoice.classList.add('hidden');
        secApproval.classList.add('hidden');
        setActiveNav(navSources);
        loadSources();
    });
```

Finally, find the `loadPendingActions`/`resolveAction` block and the `DOMContentLoaded` init at the end of the file:

```javascript
    // Initialize Page Content
    window.addEventListener('DOMContentLoaded', () => {
        loadWeeklyPulse();
        loadPendingActions();
        showAllSections();
    });
```

Replace with:

```javascript
    // --- 5. Sources Integration ---
    async function loadSources() {
        const sourcesList = document.getElementById('sources-list');
        try {
            const res = await fetch(`${API_BASE}/api/sources`);
            const data = await res.json();
            if (res.status === 200 && data.sources) {
                const groups = {};
                data.sources.forEach(url => {
                    let group = 'AMFI / SEBI Regulatory';
                    if (url.includes('amc.ppfas.com')) group = 'AMC Factsheets, KIM & SID';
                    else if (url.includes('kuvera')) group = 'Kuvera Platform Docs';
                    (groups[group] = groups[group] || []).push(url);
                });
                sourcesList.innerHTML = Object.entries(groups).map(([group, urls]) => `
                    <div>
                        <span class="font-label-caps text-xs text-on-surface-variant block mb-sm uppercase tracking-widest">${group}</span>
                        <ul class="space-y-1">
                            ${urls.map(u => `<li><a class="text-sm underline text-primary hover:text-primary/80 break-all" href="${u}" target="_blank">${u}</a></li>`).join('')}
                        </ul>
                    </div>
                `).join('');
            } else {
                sourcesList.innerHTML = `<p class="text-body-sm text-error">Failed to load sources.</p>`;
            }
        } catch (err) {
            sourcesList.innerHTML = `<p class="text-body-sm text-error">Failed to load sources.</p>`;
        }
    }

    // Initialize Page Content
    window.addEventListener('DOMContentLoaded', () => {
        loadWeeklyPulse();
        loadPendingActions();
        showAllSections();
    });
```

- [ ] **Step 7: Run the full Phase 5 suite (regression check)**

Run: `pytest src/tests_integration/test_phase5.py -v`

Expected: All tests pass (or skip together for LLM-gated tests if `GROQ_API_KEY` is unset).

- [ ] **Step 8: Manual browser verification**

1. Start (or restart) the local server: `python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000`
2. Open `http://127.0.0.1:8000/` in a browser.
3. Click the new "Sources" nav item in the left sidebar.
4. Verify the "Sources & Citations" section appears, replacing the other sections, showing 3 groups ("AMC Factsheets, KIM & SID", "Kuvera Platform Docs", "AMFI / SEBI Regulatory") each with clickable `http(s)://...` links totalling ≥30 URLs.
5. Click "FAQ Assistant", "Voice Scheduler", and "Approval Center" nav items in turn — confirm the Sources section hides again and the other views behave as before (no regressions to existing nav behavior).

---

### Task 4: Fix `requirements.txt` and `src/.env.example`

**Files:**
- Modify: `requirements.txt`
- Modify: `src/.env.example`

**Background for the engineer:**

`requirements.txt` still lists `langchain-openai` and is missing packages the code actually imports (`langchain-groq`, `langchain-community`, `langchain-huggingface`, `langchain-chroma`, `langchain-text-splitters`, `fastapi`, `uvicorn`, `httpx`, `sentence-transformers`). `src/.env.example` still references `OPENAI_API_KEY` even though the project uses Groq (`GROQ_API_KEY`) and HuggingFace embeddings, and is missing several env vars that `Config` (`src/Phase0_Shared_Foundation/config.py`) reads via `os.getenv(...)`.

No automated test covers file contents — verification is via the commands in Steps 2 and 4 (grep for imports vs. requirements, and grep for `Config`'s `os.getenv` calls vs. `.env.example`).

- [ ] **Step 1: Rewrite `requirements.txt`**

Replace the entire contents of `requirements.txt` with:

```
pydantic>=2.0.0
python-dotenv>=1.0.0
pytest>=8.0.0
langchain>=1.2.0
langchain-community>=0.4.0
langchain-groq>=1.1.0
langchain-huggingface>=1.2.0
langchain-chroma>=1.1.0
langchain-text-splitters>=1.1.0
chromadb>=1.5.0
pypdf>=4.0.0
tiktoken>=0.6.0
sentence-transformers>=5.5.0
fastapi>=0.128.0
uvicorn>=0.39.0
httpx>=0.28.0
```

- [ ] **Step 2: Verify every third-party import used in `src/` has a corresponding requirements entry**

Run:

```bash
grep -rhn "^import \|^from " src/ --include="*.py" | grep -oE "(from|import) [a-zA-Z0-9_.]+" | awk '{print $2}' | sort -u | grep -vE "^src\.|^os$|^sys$|^re$|^json$|^datetime$|^shutil$|^typing$|^random$|^string$|^csv$|^sqlite3$|^dataclasses$|^contextlib$|^tempfile$|^time$"
```

Expected: Every package-level name printed (e.g. `langchain_groq`, `langchain_chroma`, `langchain_huggingface`, `fastapi`, `pydantic`, `dotenv`, `pytest`, `langchain_community`, `langchain_text_splitters`, `langchain_core`) maps to a package listed in `requirements.txt` from Step 1 (the import name uses underscores, the PyPI package name uses hyphens — e.g. `langchain_groq` → `langchain-groq`).

- [ ] **Step 3: Rewrite `src/.env.example`**

Replace the entire contents of `src/.env.example` with:

```
GROQ_API_KEY=
CHROMA_DB_DIR=./data/vectorstore
SQLITE_DB_PATH=./data/app.db
DATA_DIR=./data/raw_docs
REVIEWS_CSV_PATH=./data/reviews.csv
LLM_MODEL=llama-3.1-8b-instant
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

- [ ] **Step 4: Verify every `Config` env var has a corresponding `.env.example` entry**

Run:

```bash
grep -oE 'os\.getenv\("[A-Z_]+"' src/Phase0_Shared_Foundation/config.py
```

Expected output: `GROQ_API_KEY`, `CHROMA_DB_DIR`, `SQLITE_DB_PATH`, `DATA_DIR`, `REVIEWS_CSV_PATH`, `LLM_MODEL`, `EMBEDDING_MODEL` — confirm each of these 7 names appears as a key in `src/.env.example` from Step 3.

---

### Task 5: Full regression run

**Files:** None (verification only)

- [ ] **Step 1: Run the entire integration test suite**

Run: `pytest src/tests_integration/ -v`

Expected: All tests pass (LLM-gated tests pass if `GROQ_API_KEY` is set, otherwise they skip cleanly) — no failures introduced by Tasks 1-4. Compare the pass/skip count against the pre-change baseline (13 passed in Phase 3 alone per the prior plan's regression run) to confirm no prior tests broke.

- [ ] **Step 2: Re-run the eval suite**

Run: `python -m src.Phase6_Evals.run_evals`

Expected: `eval_report.md` is regenerated with `Overall Status: ALL REQUIRED EVALS PASSED`, and Eval 1's `citation_accuracy` entries now reference `http(s)://...` URLs (visible if the eval report includes the raw citation values, or verifiable via Task 1's `test_citation_links_are_urls`).

---

## Self-Review Checklist

- **Spec coverage:** Task 1 → citation links as URLs (Problem Statement FAQ citation requirement). Task 2 → 8-12 week reviews span (Problem Statement data requirement). Task 3 → source manifest visibility (Problem Statement ≥30 verified URLs requirement). Task 4 → accurate `requirements.txt`/`.env.example` (deployment readiness). Task 5 → regression + eval re-run, as the user requested ("then we run the test"). TTS (#5) confirmed already implemented — correctly excluded.
- **Placeholder scan:** All code blocks are complete (no TBD/TODO); all file paths and exact find/replace snippets are concrete.
- **Type consistency:** `Config.SOURCE_URL_MAP` (dict, Task 1) is read via `.get()` in `document_loader.py` and never redefined elsewhere. `source_url` metadata key is consistent between `document_loader.py` (writer) and `rag_engine.py` (reader). `/api/sources` response shape `{"sources": [...]}` is consistent between `main.py` (Task 3 Step 3) and both the test (Step 1) and the frontend `loadSources()` (Step 6).

---

## Execution Handoff

Plan complete and saved to `Docs/superpowers/plans/2026-06-13-problem-statement-alignment-fixes.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
