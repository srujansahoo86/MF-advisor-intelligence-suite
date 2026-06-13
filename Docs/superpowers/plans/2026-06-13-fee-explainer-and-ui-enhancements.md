# Fee Explainer Wiring & UI Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining 4 gaps found in the post-Task-5 audit against `Docs/Problemstatement.md`: (1) make the M2 Fee Explainer actually retrievable by the M1 FAQ engine and exposed via API/UI, (2) surface the real voice-scheduler Booking Code in the UI, (3) add source badges to FAQ citations, and (4) enforce the "≤3 sentences / no PII" answer rules in code rather than only via prompt instructions.

**Architecture:** Backend changes follow the existing `/api/pulse`-style "persistence-or-generate-fallback" pattern in `src/api/main.py`. The `CorpusUpdater` embedding model is aligned with `RAGEngine`'s real `HuggingFaceEmbeddings` so injected Fee Explainer documents are actually retrievable via semantic search (this was previously a silent vector-space mismatch). Frontend changes are additive edits to the existing single-page `code.html` dashboard, reusing patterns already established by `loadSources()` and `loadWeeklyPulse()`. The RAG answer pipeline gets two small deterministic post-processing steps (sentence-limit truncation + PII redaction) applied to the LLM's raw output.

**Tech Stack:** Python 3.12, FastAPI, LangChain (`langchain-groq`, `langchain-huggingface`, `langchain-chroma`), ChromaDB, pytest, vanilla JS/HTML (Tailwind utility classes) in `code.html`.

---

### Task 1: Fix CorpusUpdater embedding mismatch + add `/api/fee-explainer` endpoint

**Files:**
- Modify: `src/Phase2_Review_Intelligence/corpus_updater.py`
- Modify: `src/api/main.py`
- Test: `src/tests_integration/test_phase5.py`

**Context:** `RAGEngine` (`src/Phase1_FAQ_Chatbot/rag_engine.py`) builds its `Chroma` vectorstore with `HuggingFaceEmbeddings(model_name=Config.EMBEDDING_MODEL, model_kwargs={"device": "cpu"}, encode_kwargs={"normalize_embeddings": True})`. `CorpusUpdater` (`src/Phase2_Review_Intelligence/corpus_updater.py`) currently builds its vectorstore with `DeterministicFakeEmbedding(size=384)` — a completely different vector space pointed at the *same* `Chroma` persist directory. Documents injected by `CorpusUpdater` therefore get embeddings that are meaningless relative to `RAGEngine`'s real embeddings, so the injected Fee Explainer is never actually retrievable by semantic search even though `get_injected_count()` reports it as present. Separately, there is currently no `/api/fee-explainer` endpoint at all — `Docs/Problemstatement.md` line 29-30 requires the Fee Explainer (6 bullets, 2 source links, "Last checked:" date) to be both retrievable by the FAQ engine (the "refresh mechanism", line 77) and presumably exposed for the UI.

`Persistence` (`src/Phase0_Shared_Foundation/persistence.py`) is a simple `get(key)`/`set(key, value)` SQLite KV store. `FeeExplainerGenerator.generate()` (`src/Phase2_Review_Intelligence/fee_explainer.py`) already persists its result under the key `"latest_fee_explainer"` and returns a validated `FeeExplainer` pydantic object (`bullets: List[str]` len 6, `source_links: List[str]` len 2, `last_checked: str` like `"Last checked: 2026-06-13"`).

- [ ] **Step 1: Write the failing test**

Open `src/tests_integration/test_phase5.py`. Find the last test in the file:

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

Append a new test directly after it (at the end of the file):

```python

# 7. Fee Explainer endpoint check (M2 -> M1 refresh mechanism)
def test_api_fee_explainer(clean_env):
    client = clean_env
    res = client.get("/api/fee-explainer")
    assert res.status_code == 200
    data = res.json()
    assert len(data["bullets"]) == 6
    assert len(data["source_links"]) == 2
    assert all(u.startswith("http") for u in data["source_links"])
    assert data["last_checked"].startswith("Last checked: ")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest src/tests_integration/test_phase5.py::test_api_fee_explainer -v`

Expected: FAIL — `assert res.status_code == 200` fails because `GET /api/fee-explainer` returns `404 Not Found` (no such route exists yet).

- [ ] **Step 3: Fix the CorpusUpdater embedding mismatch**

Open `src/Phase2_Review_Intelligence/corpus_updater.py`. Find these lines (1-25):

```python
from datetime import date

from langchain_core.documents import Document
from langchain_core.embeddings.fake import DeterministicFakeEmbedding
from langchain_community.vectorstores import Chroma

from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.schemas import FeeExplainer


class CorpusUpdater:
    """
    Injects a FeeExplainer into the Phase 1 ChromaDB vectorstore so the
    RAGEngine can retrieve it immediately in subsequent FAQ queries.

    IMPORTANT: Uses the same DeterministicFakeEmbedding(size=384) as Phase 1's
    RAGEngine and indexer.py to ensure vector compatibility.
    """

    def __init__(self):
        self.embeddings = DeterministicFakeEmbedding(size=384)
        self.vectorstore = Chroma(
            persist_directory=Config.CHROMA_DB_DIR,
            embedding_function=self.embeddings,
        )
```

Replace with:

```python
from datetime import date

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.schemas import FeeExplainer


class CorpusUpdater:
    """
    Injects a FeeExplainer into the Phase 1 ChromaDB vectorstore so the
    RAGEngine can retrieve it immediately in subsequent FAQ queries.

    IMPORTANT: Uses the same HuggingFaceEmbeddings(Config.EMBEDDING_MODEL) as
    Phase 1's RAGEngine to ensure the injected document is retrievable via
    semantic search.
    """

    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name=Config.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        self.vectorstore = Chroma(
            persist_directory=Config.CHROMA_DB_DIR,
            embedding_function=self.embeddings,
        )
```

The rest of the file (`add_fee_explainer` and `get_injected_count` methods) is unchanged.

- [ ] **Step 4: Add the `/api/fee-explainer` endpoint**

Open `src/api/main.py`. Find the import block at the top (lines 1-6):

```python
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
```

Replace with:

```python
import os
from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
```

Now find the end of `get_weekly_pulse()` and the start of `get_sources()` (lines 89-95):

```python
        return pulse
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sources")
def get_sources():
    return {"sources": sorted(Config.SOURCE_MANIFEST_URLS)}
```

Replace with:

```python
        return pulse
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fee-explainer")
def get_fee_explainer():
    try:
        persistence = Persistence()
        explainer = persistence.get("latest_fee_explainer")
        if not explainer:
            # Generate dynamically from reviews.csv if database store is empty,
            # and refresh the FAQ retrieval corpus (M2 -> M1 refresh mechanism)
            csv_path = Config.REVIEWS_CSV_PATH
            if os.path.exists(csv_path):
                from src.Phase2_Review_Intelligence.review_processor import ReviewProcessor
                from src.Phase2_Review_Intelligence.fee_explainer import FeeExplainerGenerator
                from src.Phase2_Review_Intelligence.corpus_updater import CorpusUpdater

                processor = ReviewProcessor(csv_path)
                reviews = processor.load()
                gen = FeeExplainerGenerator()
                explainer_obj = gen.generate(reviews)
                explainer = explainer_obj.model_dump()

                CorpusUpdater().add_fee_explainer(explainer_obj)
            else:
                explainer = {
                    "bullets": [
                        "Expense ratio (TER) is the annual fee a fund charges to cover management and operating costs.",
                        "Direct plans have a lower expense ratio than regular plans because they cut out distributor commission.",
                        "Exit load is a fee charged if you redeem units before a scheme's minimum holding period.",
                        "Stamp duty of 0.005% is deducted from every mutual fund purchase, including SIP instalments.",
                        "ELSS and other lock-in funds restrict withdrawals until the lock-in period ends.",
                        "A lower expense ratio means more of your returns stay invested and compound over time."
                    ],
                    "source_links": [
                        Config.FEE_EXPLAINER_AMFI_URL,
                        Config.FEE_EXPLAINER_SEBI_URL,
                    ],
                    "last_checked": f"Last checked: {date.today().isoformat()}"
                }
        return explainer
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sources")
def get_sources():
    return {"sources": sorted(Config.SOURCE_MANIFEST_URLS)}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest src/tests_integration/test_phase5.py::test_api_fee_explainer -v`

Expected: PASS. Note this will make a real Groq API call (via `FeeExplainerGenerator`) since `latest_fee_explainer` is not yet persisted and `data/reviews.csv` exists — this is consistent with how `test_api_pulse` already exercises `PulseGenerator` for real.

- [ ] **Step 6: Run the broader regression for Phase 2 and Phase 5**

Run: `python -m pytest src/tests_integration/test_phase2.py src/tests_integration/test_phase5.py -v`

Expected: All tests pass, including the pre-existing `test_corpus_updater_injects_document` and `test_full_pipeline` (Phase 2), confirming the embedding change did not break document injection.

---

### Task 2: Frontend UI — Fee Explainer section, Booking Code display, FAQ source badges

**Files:**
- Modify: `stitch_mf_advisor_intelligence_suite/code.html`

**Context:** This task makes three independent, additive edits to the single-page dashboard `code.html`:
1. A new "Fee Explainer" subsection inside the Weekly Pulse panel (`section-pulse`), populated from the new `/api/fee-explainer` endpoint (Task 1) via a new `loadFeeExplainer()` JS function — mirroring the existing `loadSources()`/`loadWeeklyPulse()` pattern.
2. The hardcoded `ID: VS-7721-OP` badge in the Voice Scheduler panel (`section-voice`) is replaced with a placeholder that gets populated with the real `booking_code` (format `KV-XXXX`) returned by `POST /api/voice` once a booking is made.
3. FAQ citation links (rendered in `appendMessage()`) get a small "source badge" label (e.g. `AMC Factsheet`, `Kuvera`, `AMFI/SEBI`) derived from the citation URL's domain, using the same grouping logic already used by `loadSources()`.

- [ ] **Step 1: Add the Fee Explainer HTML subsection to the Pulse panel**

In `stitch_mf_advisor_intelligence_suite/code.html`, find this block inside `<section id="section-pulse" ...>`:

```html
<div id="pulse-quotes" class="grid grid-cols-1 sm:grid-cols-2 gap-xs">
<div class="p-md bg-primary-container/20 rounded-xl border-l-4 border-primary shadow-sm">
<span class="font-label-caps text-[10px] text-primary font-bold uppercase">Recent Client Feedback</span>
<p class="text-body-sm text-on-surface italic mt-xs font-medium">"I need a clearer breakdown of the carbon offset costs in the Green Portfolio B..."</p>
</div>
</div>
<div class="space-y-md">
<span class="font-label-caps text-xs text-on-surface-variant uppercase tracking-widest">Recommended Actions</span>
```

Replace with (inserting a new Fee Explainer block between the quotes and the Recommended Actions section):

```html
<div id="pulse-quotes" class="grid grid-cols-1 sm:grid-cols-2 gap-xs">
<div class="p-md bg-primary-container/20 rounded-xl border-l-4 border-primary shadow-sm">
<span class="font-label-caps text-[10px] text-primary font-bold uppercase">Recent Client Feedback</span>
<p class="text-body-sm text-on-surface italic mt-xs font-medium">"I need a clearer breakdown of the carbon offset costs in the Green Portfolio B..."</p>
</div>
</div>
<div>
<span class="font-label-caps text-xs text-on-surface-variant block mb-sm uppercase tracking-widest">Fee Explainer</span>
<div id="fee-explainer" class="p-md bg-surface-container rounded-xl border border-outline/10 space-y-2">
<p class="text-body-sm text-on-surface-variant">Loading fee explainer...</p>
</div>
</div>
<div class="space-y-md">
<span class="font-label-caps text-xs text-on-surface-variant uppercase tracking-widest">Recommended Actions</span>
```

- [ ] **Step 2: Replace the hardcoded Booking Code badge in the Voice panel**

In the same file, find this block inside `<section id="section-voice" ...>`:

```html
<div class="flex items-center gap-xs">
<span class="text-xs font-mono-data text-primary font-bold tracking-[0.2em] bg-primary/5 px-4 py-2 rounded-lg border border-primary/10">ID: VS-7721-OP</span>
</div>
```

Replace with:

```html
<div class="flex items-center gap-xs">
<span id="booking-code-badge" class="text-xs font-mono-data text-primary font-bold tracking-[0.2em] bg-primary/5 px-4 py-2 rounded-lg border border-primary/10">No active booking</span>
</div>
```

- [ ] **Step 3: Add a `getSourceBadge()` helper and use it in FAQ citation rendering**

Find this block (the start of the `appendMessage` function):

```javascript
    function appendMessage(sender, text, citations = [], clarificationQuestions = []) {
```

Replace with (adding a helper function immediately before it):

```javascript
    function getSourceBadge(url) {
        if (url.includes('amc.ppfas.com')) return 'AMC Factsheet';
        if (url.includes('kuvera')) return 'Kuvera';
        return 'AMFI/SEBI';
    }

    function appendMessage(sender, text, citations = [], clarificationQuestions = []) {
```

Now find the citation rendering block inside `appendMessage`:

```javascript
            let citationHtml = "";
            if (citations && citations.length > 0) {
                citationHtml = `
                    <div class="mt-xs p-sm bg-surface-container rounded-xl border border-outline/10 text-[11px] text-on-surface-variant">
                        <p class="font-bold text-primary mb-1">Sources & Citations:</p>
                        <ul class="list-disc ml-xs space-y-1">
                            ${citations.map(c => `<li><a class="underline hover:text-primary" href="${c}" target="_blank">${c}</a></li>`).join('')}
                        </ul>
                    </div>
                `;
            }
```

Replace with:

```javascript
            let citationHtml = "";
            if (citations && citations.length > 0) {
                citationHtml = `
                    <div class="mt-xs p-sm bg-surface-container rounded-xl border border-outline/10 text-[11px] text-on-surface-variant">
                        <p class="font-bold text-primary mb-1">Sources & Citations:</p>
                        <ul class="list-disc ml-xs space-y-1">
                            ${citations.map(c => `<li><span class="inline-block bg-primary/10 text-primary text-[10px] font-bold px-2 py-0.5 rounded mr-1 uppercase">${getSourceBadge(c)}</span><a class="underline hover:text-primary" href="${c}" target="_blank">${c}</a></li>`).join('')}
                        </ul>
                    </div>
                `;
            }
```

- [ ] **Step 4: Add `feeExplainerDiv` and `bookingCodeBadge` element references**

Find this block:

```javascript
    const pulseThemes = document.getElementById('pulse-themes');
    const pulseQuotes = document.getElementById('pulse-quotes');
    const pulseActions = document.getElementById('pulse-actions');
```

Replace with:

```javascript
    const pulseThemes = document.getElementById('pulse-themes');
    const pulseQuotes = document.getElementById('pulse-quotes');
    const pulseActions = document.getElementById('pulse-actions');
    const feeExplainerDiv = document.getElementById('fee-explainer');
```

Find this block:

```javascript
    const micButton = document.getElementById('mic-button');
    const transcriptText = document.getElementById('transcript-text');
```

Replace with:

```javascript
    const micButton = document.getElementById('mic-button');
    const transcriptText = document.getElementById('transcript-text');
    const bookingCodeBadge = document.getElementById('booking-code-badge');
```

- [ ] **Step 5: Add `loadFeeExplainer()` function**

Find this block (the end of `loadWeeklyPulse()`):

```javascript
        } catch (err) {
            console.error("Failed to load Weekly Pulse:", err);
        }
    }


    // --- 3. Voice Scheduler Integration ---
```

Replace with:

```javascript
        } catch (err) {
            console.error("Failed to load Weekly Pulse:", err);
        }
    }

    async function loadFeeExplainer() {
        try {
            const res = await fetch(`${API_BASE}/api/fee-explainer`);
            const data = await res.json();
            if (res.status === 200 && data.bullets) {
                feeExplainerDiv.innerHTML = `
                    <ul class="list-disc ml-md space-y-1 text-body-sm text-on-surface">
                        ${data.bullets.map(b => `<li>${b}</li>`).join('')}
                    </ul>
                    <div class="pt-xs border-t border-outline/10 flex flex-wrap gap-md items-center justify-between">
                        <div class="flex flex-wrap gap-sm">
                            ${data.source_links.map(u => `<a class="text-xs underline text-primary hover:text-primary/80" href="${u}" target="_blank">${u}</a>`).join('')}
                        </div>
                        <span class="text-[10px] text-on-surface-variant font-mono-data">${data.last_checked}</span>
                    </div>
                `;
            } else {
                feeExplainerDiv.innerHTML = `<p class="text-body-sm text-error">Failed to load fee explainer.</p>`;
            }
        } catch (err) {
            feeExplainerDiv.innerHTML = `<p class="text-body-sm text-error">Failed to load fee explainer.</p>`;
        }
    }


    // --- 3. Voice Scheduler Integration ---
```

- [ ] **Step 6: Display the real Booking Code after a successful voice booking**

Find this block inside `sendVoiceTranscript`:

```javascript
            if (res.status === 200) {
                transcriptText.textContent = data.message;
                
                // Read confirmation back aloud (TTS)
```

Replace with:

```javascript
            if (res.status === 200) {
                transcriptText.textContent = data.message;

                if (data.booking_code) {
                    bookingCodeBadge.textContent = `Booking Code: ${data.booking_code}`;
                }

                // Read confirmation back aloud (TTS)
```

- [ ] **Step 7: Call `loadFeeExplainer()` on page load**

Find this block:

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
    // Initialize Page Content
    window.addEventListener('DOMContentLoaded', () => {
        loadWeeklyPulse();
        loadFeeExplainer();
        loadPendingActions();
        showAllSections();
    });
```

- [ ] **Step 8: Manual verification**

Start the API server (`python -m uvicorn src.api.main:app --reload` from the project root) and open `http://127.0.0.1:8000/` in a browser. Verify:
- The Weekly Pulse panel shows a new "Fee Explainer" box with 6 bullets, 1-2 source links, and a "Last checked: ..." stamp.
- The Voice Scheduler panel shows "No active booking" initially; after recording/typing a scheduling request that results in a booking, it updates to show "Booking Code: KV-XXXX".
- Asking the FAQ chatbot a factual question (e.g. "What is the exit load for Parag Parikh Liquid Fund?") renders a citation with a badge label (e.g. "AMC Factsheet" or "AMFI/SEBI") before the link.

---

### Task 3: Enforce ≤3-sentence answers and PII redaction in RAGEngine

**Files:**
- Modify: `src/Phase1_FAQ_Chatbot/rag_engine.py`
- Test: `src/tests_integration/test_phase1.py`

**Context:** `Docs/Problemstatement.md` line 25 requires: "Answers must be ≤ 3 sentences. No performance claims. No PII collected." Currently `RAGEngine.answer_query()` only *asks* the LLM (via prompt instruction "Answer concisely in 1-3 sentences") to keep answers short, and does not redact PII from the LLM's output at all. This task adds two deterministic post-processing steps applied to the raw LLM response: a sentence-count truncation helper, and PII redaction via the existing `redact_pii()` function (`src/Phase0_Shared_Foundation/pii.py`), which already redacts emails, PAN numbers, folio numbers, phone numbers, and location+PIN combinations.

- [ ] **Step 1: Write the failing unit tests**

Open `src/tests_integration/test_phase1.py`. The file currently ends with:

```python
def test_citation_links_are_urls(rag_engine):
    """Citations must be clickable source URLs, not raw PDF filenames."""
    ans = rag_engine.answer_query("What is the exit load for Parag Parikh Liquid Fund?")
    assert len(ans.citation_links) > 0
    for link in ans.citation_links:
        assert link.startswith("http"), f"Citation '{link}' is not a URL"
```

Append the following at the end of the file:

```python


def test_enforce_sentence_limit_truncates_long_text():
    """Responses longer than 3 sentences must be truncated to enforce the spec's '<=3 sentences' rule."""
    long_text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    result = RAGEngine._enforce_sentence_limit(long_text, max_sentences=3)
    assert result == "First sentence. Second sentence. Third sentence."


def test_enforce_sentence_limit_passes_short_text_through():
    """Text within the sentence limit must be returned unchanged."""
    short_text = "Only one sentence here."
    result = RAGEngine._enforce_sentence_limit(short_text, max_sentences=3)
    assert result == short_text


def test_enforce_sentence_limit_handles_questions_and_exclamations():
    """Sentence splitting must handle '?' and '!' terminators, not just '.'."""
    text = "Is this safe? Yes it is! Here's why. And more detail follows here."
    result = RAGEngine._enforce_sentence_limit(text, max_sentences=3)
    assert result == "Is this safe? Yes it is! Here's why."
```

These call `RAGEngine._enforce_sentence_limit` as a `@staticmethod` directly on the class (no `RAGEngine()` instantiation needed), so they run without `GROQ_API_KEY` and without loading embeddings/vectorstore — fast, deterministic, never skipped.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest src/tests_integration/test_phase1.py::test_enforce_sentence_limit_truncates_long_text -v`

Expected: FAIL — `AttributeError: type object 'RAGEngine' has no attribute '_enforce_sentence_limit'`.

- [ ] **Step 3: Add `import re` and `redact_pii` import to rag_engine.py**

Open `src/Phase1_FAQ_Chatbot/rag_engine.py`. Find the import block (lines 1-6):

```python
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.schemas import Answer
from src.Phase0_Shared_Foundation.guardrails import Guardrails
```

Replace with:

```python
import re

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.schemas import Answer
from src.Phase0_Shared_Foundation.guardrails import Guardrails
from src.Phase0_Shared_Foundation.pii import redact_pii
```

(Note: a different method in this file, `_retrieve_context`, has its own local `import re` further down — leave that line as-is; the new module-level `import re` is additive and harmless.)

- [ ] **Step 4: Add the `_enforce_sentence_limit` static method**

Find this block (end of `__init__`, start of `_check_ambiguity`):

```python
        self.llm = ChatGroq(model_name=Config.LLM_MODEL, temperature=0.0)
        
    def _check_ambiguity(self, query: str) -> list[str]:
```

Replace with:

```python
        self.llm = ChatGroq(model_name=Config.LLM_MODEL, temperature=0.0)

    @staticmethod
    def _enforce_sentence_limit(text: str, max_sentences: int = 3) -> str:
        """Truncates text to at most max_sentences sentences."""
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        if len(sentences) <= max_sentences:
            return text
        return " ".join(sentences[:max_sentences])

    def _check_ambiguity(self, query: str) -> list[str]:
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest src/tests_integration/test_phase1.py::test_enforce_sentence_limit_truncates_long_text src/tests_integration/test_phase1.py::test_enforce_sentence_limit_passes_short_text_through src/tests_integration/test_phase1.py::test_enforce_sentence_limit_handles_questions_and_exclamations -v`

Expected: All 3 PASS.

- [ ] **Step 6: Apply both enforcements to the final answer in `answer_query`**

Find this block (the end of `answer_query`):

```python
        response_text = self.llm.invoke(qa_prompt).content.strip()

        # Clear sources if the LLM admitted it didn't find the answer
        if "verified source for that" in response_text:
            sources = []

        return Answer(
            text=response_text,
            citation_links=sources
        )
```

Replace with:

```python
        response_text = self.llm.invoke(qa_prompt).content.strip()
        response_text = redact_pii(response_text)
        response_text = self._enforce_sentence_limit(response_text, max_sentences=3)

        # Clear sources if the LLM admitted it didn't find the answer
        if "verified source for that" in response_text:
            sources = []

        return Answer(
            text=response_text,
            citation_links=sources
        )
```

- [ ] **Step 7: Run the full Phase 1 test suite**

Run: `python -m pytest src/tests_integration/test_phase1.py -v`

Expected: All tests pass (LLM-gated tests run for real since `GROQ_API_KEY` is set; `test_guardrails_integration`, `test_ambiguity_check`, `test_missing_info`, `test_citation_links_are_urls`, and the 3 new sentence-limit tests all pass).

---

### Task 4: Full regression run

**Files:** None (verification only)

- [ ] **Step 1: Run the entire integration test suite**

Run: `python -m pytest src/tests_integration/ -v`

Expected: All tests pass — no failures introduced by Tasks 1-3. The suite should now show 48 passed (44 from the prior plan's regression + 1 new `test_api_fee_explainer` + 3 new `_enforce_sentence_limit` unit tests).

- [ ] **Step 2: Re-run the eval suite**

Run: `python -m src.Phase6_Evals.run_evals`

Expected: `eval_report.md` is regenerated with `Overall Status: ALL REQUIRED EVALS PASSED`. Eval 1 (RAG) answers should still satisfy citation and tone checks; Eval 3 (tone) answers should now be visibly ≤3 sentences due to Task 3's enforcement.

---

## Self-Review Checklist

- **Spec coverage:** Task 1 → Fee Explainer retrievable by M1 + exposed via `/api/fee-explainer` (Problem Statement lines 29-30, 77). Task 2 → Fee Explainer UI in Pulse view, Booking Code in Scheduler view, source badges in FAQ view (Problem Statement lines 22, 43-47). Task 3 → "≤3 sentences, no PII" enforcement (Problem Statement line 25). Task 4 → regression + eval re-run.
- **Placeholder scan:** All code blocks are complete (no TBD/TODO); all file paths and exact find/replace snippets are concrete and were verified against the current file contents.
- **Type consistency:** `CorpusUpdater.__init__` now uses `HuggingFaceEmbeddings(model_name=Config.EMBEDDING_MODEL, ...)` identical to `RAGEngine.__init__`. `/api/fee-explainer` response shape (`bullets`, `source_links`, `last_checked`) matches `FeeExplainer.model_dump()` and is consumed identically by `loadFeeExplainer()`. `RAGEngine._enforce_sentence_limit` is referenced consistently as a `@staticmethod` in both the implementation (Task 3 Step 4) and the test calls (Task 3 Step 1, `RAGEngine._enforce_sentence_limit(...)`).

---
