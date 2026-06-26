import re
from functools import lru_cache

from langchain_groq import ChatGroq
from langchain_chroma import Chroma
from src.Phase0_Shared_Foundation.config import Config
from src.Phase0_Shared_Foundation.schemas import Answer
from src.Phase0_Shared_Foundation.guardrails import Guardrails
from src.Phase0_Shared_Foundation.pii import redact_pii

class RAGEngine:
    """Core Retrieval-Augmented Generation Engine for factual FAQ."""
    def __init__(self):
        from langchain_community.embeddings import FastEmbedEmbeddings
        self.embeddings = FastEmbedEmbeddings(model_name=Config.EMBEDDING_MODEL)
        self.vectorstore = Chroma(
            persist_directory=Config.CHROMA_DB_DIR,
            embedding_function=self.embeddings,
        )
        self.llm = ChatGroq(model_name=Config.LLM_MODEL, temperature=0.0)

    @staticmethod
    def _enforce_sentence_limit(text: str, max_sentences: int = 3) -> str:
        """Truncates text to at most max_sentences sentences."""
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        if len(sentences) <= max_sentences:
            return text
        return " ".join(sentences[:max_sentences])

    def _check_ambiguity(self, query: str) -> list[str]:
        """
        Lightweight check to see if the mutual fund scheme is ambiguous.
        Returns a list of up to 3 clarifying questions.

        Logic (in order):
          1. Clarification-answer passthrough ("My answer:" prefix)
          2. METRIC GATE: if query has no specific metric keyword → not ambiguous, return []
          3. CATALOG / GENERAL fast-path keywords → return []
          4. Named-fund check → return []
          5. LLM edge-case classifier (only reached for metric queries with no named fund)
        """
        # 1. If this query is a clarification answer sent from UI context, pass through.
        if "My answer:" in query:
            return []

        q_lower = query.lower().strip()

        # 2. ── METRIC GATE (first and most important check) ──────────────────
        # Ambiguity only matters for fund-specific metrics (exit load, NAV, etc.)
        # A query with NO metric keyword is ALWAYS a general question — never ambiguous.
        METRIC_KEYWORDS = [
            "exit load", "expense ratio", "nav", "net asset value",
            "minimum investment", "minimum sip", "minimum lump", "aum",
            "returns", "performance", "rating", "risk grade", "benchmark",
            "lock in period", "lock-in", "dividend", "idcw",
            "riskometer", "risk-o-meter", "risk o meter",
            "tax residency", "fatca", "crs"
        ]
        asks_for_metric = any(kw in q_lower for kw in METRIC_KEYWORDS)
        if not asks_for_metric:
            return []   # <-- "which funds do you have?", "what is a liquid fund?", etc. all exit here

        # 3. ── Catalog / general fast-path ──────────────────────────────────
        # Even within metric-ish queries, these patterns indicate a general question.
        ALWAYS_SPECIFIC_KEYWORDS = [
            # Catalog / listing questions
            "which funds", "what funds", "list of funds", "list funds",
            "funds do you have", "funds available", "funds you have",
            "which schemes", "what schemes", "available funds", "available schemes",
            "show funds", "show schemes",
            # Platform / process questions
            "how do i", "how to", "how can i", "where do i", "when will",
            "capital gains", "tax statement", "sip", "switch", "redeem",
            "redemption", "direct plan", "regular plan", "elss", "lock-in",
            "commission", "account", "login", "sign up", "register",
            "download", "report", "portfolio",
            "ter mean", "what is ter", "expense ratio mean", "what is expense ratio",
            # Greetings / general
            "hello", "hi ", "help", "what can you", "what do you",
            "tell me about", "explain", "what is amfi", "what is sebi",
        ]
        for kw in ALWAYS_SPECIFIC_KEYWORDS:
            if kw in q_lower:
                return []

        # 4. ── Named-fund check ───────────────────────────────────────────────
        KNOWN_FUNDS = [
            "parag parikh", "ppfas", "hdfc", "icici", "sbi", "axis", "kotak",
            "mirae", "nippon", "tata", "dsp", "aditya birla", "franklin",
            "uti", "quantum", "motilal", "invesco", "bandhan",
            "liquid fund", "arbitrage fund", "hybrid fund", "large cap",
            "mid cap", "small cap", "flexi cap", "flexi", "dynamic asset",
            "liquid", "arbitrage", "conservative", "dynamic",
        ]
        names_a_fund = any(kw in q_lower for kw in KNOWN_FUNDS)
        if names_a_fund:
            return []

        # 5. ── LLM edge-case classifier ──────────────────────────────────────
        # Only reached when query asks for a specific metric AND names no fund.
        ambiguity_prompt = f"""You are a strict query classifier for a mutual fund FAQ system.

CLASSIFICATION RULES:
1. Output ONLY the word SPECIFIC if the query:
   - Names a specific mutual fund scheme (e.g., "Parag Parikh Liquid Fund", "HDFC Mid Cap")
   - Names a specific AMC (e.g., "PPFAS", "HDFC AMC")
   - Is a general/catalog/informational question (e.g., "which funds do you have?", "what is a liquid fund?")
   - Is a general process/platform question (e.g., "How do I download capital gains?", "How do I start a SIP?")
   - Is an administrative/account question that doesn't need a fund name

2. Output 1 to 3 clarifying questions (one per line, each starting with "- ") ONLY if the query:
   - Asks about a specific numeric/performance metric (exit load, NAV, expense ratio, returns, minimum investment)
   - AND does NOT mention any specific fund name or AMC

WHEN IN DOUBT — output SPECIFIC. Only flag as ambiguous if clearly a metric question with no fund named.

IMPORTANT: Your response MUST be either:
   a) The single word: SPECIFIC
   b) 1-3 lines starting with "- " that are questions asking the user to name their specific fund

Do NOT output code, explanations, or anything else. Just SPECIFIC or the bullet questions.

Query to classify: "{query}"

Your classification:"""

        response = self.llm.invoke(ambiguity_prompt).content.strip()

        # If response contains code blocks, it's a malformed response — treat as SPECIFIC
        if "```" in response or "def " in response or "return " in response:
            return []

        # Check if the ENTIRE response is just "SPECIFIC" (case-insensitive)
        if response.strip().upper() == "SPECIFIC":
            return []

        # Also bail out if the first line is a solo "SPECIFIC" keyword
        first_line = response.split("\n")[0].strip()
        if first_line.upper() == "SPECIFIC":
            return []

        # Parse: handle bullet lines, numbered lines, or plain sentences
        lines = [l.strip() for l in response.split("\n") if l.strip()]
        questions = []
        for line in lines:
            # Strip common list prefixes: "- ", "1. ", "1) "
            clean = line.lstrip("0123456789.-) ").strip()
            # Skip lines that are solely the word SPECIFIC or contain code artifacts
            if clean and clean.upper() != "SPECIFIC" and "def " not in clean and "return " not in clean:
                questions.append(clean)

        return questions[:3]

    # Financial term synonyms — used by hybrid re-ranker + query expansion
    _TERM_SYNONYMS = {
        # Metric terms
        "exit load":        ["exit load", "redemption charge", "exit fee", "exit penalty"],
        "expense ratio":    ["expense ratio", "ter", "total expense ratio", "annual charge"],
        "nav":              ["nav", "net asset value", "unit price"],
        "aum":              ["aum", "assets under management", "fund size"],
        "minimum sip":      ["minimum sip", "min sip", "minimum installment", "minimum amount"],
        "minimum lump":     ["minimum lump", "minimum one-time", "lumpsum minimum", "minimum purchase"],
        "lock-in":          ["lock-in", "lock in period", "lockin"],
        "dividend":         ["dividend", "idcw", "income distribution"],
        "benchmark":        ["benchmark", "nifty", "sensex", "crisil"],
        "returns":          ["returns", "cagr", "annualised return", "performance"],
        "riskometer":       ["riskometer", "risk-o-meter", "risk o meter", "risk level", "suitability"],
        "tax residency":    ["tax residency", "fatca", "crs", "non-resident", "nri", "foreign investor", "nationality"],
        # Fund name aliases
        "flexi":            ["flexi cap", "flexi", "parag parikh flexi"],
        "liquid":           ["liquid fund", "parag parikh liquid", "open-ended liquid"],
        "arbitrage":        ["arbitrage fund", "parag parikh arbitrage"],
        "conservative":     ["conservative hybrid", "parag parikh conservative"],
        "large cap":        ["large cap fund", "parag parikh large cap", "largecap"],
        "dynamic":          ["dynamic asset allocation", "parag parikh dynamic"],
        # Platform / process query keywords → steer to Kuvera docs
        "capital gains":    ["capital gains", "capital gain report", "tax report", "gains statement"],
        "download":         ["download", "get my", "access my", "generate report"],
        "switch":           ["switch", "regular to direct", "switch mutual fund"],
        "redeem":           ["redeem", "redemption", "withdraw"],
        "sip cancel":       ["cancel sip", "stop sip", "pause sip"],
        "elss":             ["elss", "equity linked savings", "tax saving fund", "lock-in", "80c"],
    }

    # Funds NOT offered by Parag Parikh — return a helpful message instead of RAG
    _NOT_OFFERED_PATTERNS = [
        ("elss", "Parag Parikh does not currently offer an ELSS (Equity Linked Savings Scheme) fund. "
                 "Our 5 schemes are: Liquid, Arbitrage, Conservative Hybrid, Large Cap, and Dynamic Asset Allocation. "
                 "For ELSS investments, please visit AMFI: https://www.amfiindia.com"),
        ("mid cap", "Parag Parikh does not offer a dedicated mid cap fund. "
                    "Our closest equity option is the Parag Parikh Flexi Cap Fund which invests across market caps."),
        ("small cap", "Parag Parikh does not offer a small cap fund. "
                      "Our equity schemes are the Large Cap Fund and Flexi Cap Fund."),
    ]

    def _retrieve_context(self, query: str, k: int = 5) -> list:
        """
        Hybrid retrieval with query expansion:
          1. Expand the query with financial synonyms so the semantic model
             gets the right vocabulary (e.g. 'redemption charge' → 'exit load').
          2. Run semantic search on expanded query to get top-30 candidates.
          3. Keyword re-rank candidates by presence of financial terms.
          4. Return top-k re-ranked docs.
        """
        try:
            import re
            q_lower = query.lower()

            # Step 1 — Query expansion using synonym map
            expansion_terms: list[str] = []
            for canonical, synonyms in self._TERM_SYNONYMS.items():
                if any(s in q_lower for s in synonyms):
                    expansion_terms.extend(synonyms)

            expanded_query = query
            if expansion_terms:
                # Append unique synonyms not already in query to help semantic search
                extras = [t for t in expansion_terms if t not in q_lower]
                if extras:
                    expanded_query = query + " " + " ".join(set(extras))

            # Step 2 — Semantic search on expanded query (large candidate pool)
            candidates = self.vectorstore.similarity_search(expanded_query, k=100)
            if not candidates:
                return []

            # Step 3 — Build keyword boost set (expansion terms + raw query words)
            _sw = {"what","is","the","for","with","this","that","about","your",
                   "have","you","are","and","can","how","does","mean","which",
                   "fund","funds","scheme","mutual","plan","tell","show","give"}
            raw_words = [w for w in re.findall(r'\b[a-z]{3,}\b', q_lower) if w not in _sw]
            boost_terms = list(set(expansion_terms + raw_words))

            # Step 4 — Score and re-rank candidates
            seen, scored = set(), []
            for doc in candidates:
                # Deduplicate by content hash
                key = doc.page_content[:80]
                if key in seen:
                    continue
                seen.add(key)
                text = doc.page_content.lower()
                score = 0
                for term in boost_terms:
                    if term in text:
                        score += len(term.split())  # multi-word terms score higher
                scored.append((score, doc))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [doc for _, doc in scored[:k]]

        except Exception as e:
            print(f"[RAGEngine] Hybrid retrieval failed: {e}")
            return []

    # Fund catalog — single source of truth for "which funds do you offer" questions
    FUND_CATALOG = [
        "1. **Parag Parikh Liquid Fund** — Low-risk, open-ended liquid scheme. Ideal for short-term parking of surplus cash.",
        "2. **Parag Parikh Arbitrage Fund** — Open-ended arbitrage scheme. Exploits price differentials between cash and derivatives markets.",
        "3. **Parag Parikh Conservative Hybrid Fund** — Open-ended hybrid scheme investing predominantly in debt instruments with limited equity exposure.",
        "4. **Parag Parikh Large Cap Fund** — Open-ended large cap equity scheme focusing on the top 100 companies by market capitalisation.",
        "5. **Parag Parikh Dynamic Asset Allocation Fund** — Open-ended dynamic asset allocation scheme that shifts between equity and debt based on market conditions.",
    ]

    # Patterns that signal a fund-listing / catalog question
    # NOTE: patterns are written in *singular* form; _is_catalog_query normalises
    # the query by stripping a trailing 's' from "funds"→"fund" / "schemes"→"scheme"
    # before matching, so both singular and plural forms are caught automatically.
    _CATALOG_PATTERNS = [
        "which fund", "what fund", "which all fund", "list of fund", "list fund",
        "fund do you have", "fund you have", "fund available", "available fund",
        "which scheme", "what scheme", "all scheme", "scheme available",
        "show fund", "show me fund", "tell me fund", "give me fund",
        "how many fund", "types of fund", "type of fund",
        "what all fund", "all fund", "all the fund",
        # Plain-English variants — scoped to fund/scheme listing only
        "fund do you offer", "fund you offer", "fund you provide",
        "what fund do", "what fund can",
    ]

    # Queries asking for recommendations/comparison — handled with a soft advisory disclaimer
    _ADVISORY_PATTERNS = [
        "which is best", "which one is best", "which fund is best",
        "best fund", "best scheme", "recommend", "suggest",
        "compare", "comparison", "better fund", "which to choose",
        "should i pick", "which one should",
    ]

    def _is_catalog_query(self, query: str) -> bool:
        """Returns True if the query is asking for a listing of available funds."""
        q = query.lower()
        # If the query asks for a specific metric, it is NOT a simple catalog query.
        METRIC_KEYWORDS = [
            "exit load", "expense ratio", "nav", "net asset value", "ter",
            "minimum investment", "minimum sip", "minimum lump", "aum",
            "returns", "performance", "rating", "risk grade", "benchmark",
            "lock in period", "lock-in", "dividend", "idcw", "riskometer",
            "risk-o-meter", "risk o meter", "tax residency", "fatca", "crs"
        ]
        if any(kw in q for kw in METRIC_KEYWORDS):
            return False
        # Normalise plural → singular so one set of patterns covers both forms
        # e.g. "funds" → "fund", "schemes" → "scheme"
        q_norm = q.replace("funds", "fund").replace("schemes", "scheme")
        return any(pat in q_norm for pat in self._CATALOG_PATTERNS)

    def _is_advisory_query(self, query: str) -> bool:
        """Returns True if the query is asking for fund recommendations or comparisons."""
        q = query.lower()
        return any(pat in q for pat in self._ADVISORY_PATTERNS)

    def answer_query(self, query: str) -> Answer:
        # 1. Guardrails check (Fast path failure)
        is_safe, refusal_msg = Guardrails.check_query(query)
        if not is_safe:
            return Answer(
                text=refusal_msg,
                citation_links=[],
                is_safe=False,
                refusal_message=refusal_msg
            )

        # 1b. Advisory / comparison fast-path — soft disclaimer before RAG
        if self._is_advisory_query(query):
            return Answer(
                text=(
                    "I'm not able to recommend or rank specific funds — that would be "
                    "personalised investment advice, which requires a registered advisor. "
                    "I can share factual details (exit loads, NAV, expense ratios, minimum SIP) "
                    "for any of our 5 Parag Parikh schemes if you'd like to compare them yourself."
                ),
                citation_links=["https://www.amfiindia.com/investor-corner"],
                is_safe=True
            )

        # 2. Catalog fast-path — answer "which funds do you have" without RAG
        if self._is_catalog_query(query):
            catalog_text = (
                "We currently offer **5 Parag Parikh mutual fund schemes**:\n\n"
                + "\n".join(self.FUND_CATALOG)
                + "\n\nYou can ask me for details on any specific fund — exit loads, "
                  "expense ratios, NAV, minimum SIP, etc."
            )
            return Answer(
                text=catalog_text,
                citation_links=["https://amc.ppfas.com"]
            )
            
        # 3. Ambiguity check (Conversational turning)
        clarification_questions = self._check_ambiguity(query)
        if clarification_questions:
            return Answer(
                text="I need a bit more detail to give you the right answer.",
                citation_links=[],
                needs_clarification=True,
                clarification_questions=clarification_questions
            )
            
        # 4a. Not-offered fund fast-path — avoids misleading retrieval
        q_lower = query.lower()
        for pattern, message in self._NOT_OFFERED_PATTERNS:
            if pattern in q_lower:
                return Answer(text=message, citation_links=["https://www.amfiindia.com/investor-corner"])

        # 4b. Retrieval
        docs = self._retrieve_context(query, k=10)
        if not docs:
            return Answer(
                text="I don't have a verified source for that.",
                citation_links=[]
            )

        context = "\n\n".join([f"Source: {d.metadata.get('source', 'Unknown')}\n{d.page_content}" for d in docs])
        sources = list(set([d.metadata.get('source_url', d.metadata.get('source', 'Unknown')) for d in docs]))

        # 5. Generation
        qa_prompt = f"""You are a knowledgeable AI assistant for a mutual fund advisory platform (Kuvera / Parag Parikh AMC).

Your job is to answer the user's question using ONLY the context provided below.

Rules:
1. Answer concisely in 1-3 sentences.
2. For HOW-TO / process questions (e.g. "how do I download", "how to redeem"), give step-by-step guidance if the context has it.
3. For factual metric questions (NAV, exit load, expense ratio), quote the exact figure from the context.
4. If the context does NOT contain enough information to answer, reply EXACTLY with: "I don't have a verified source for that."
5. Do NOT make up facts. Do NOT use outside knowledge.

Context:
{context}

Question: {query}

Answer:"""

        response_text = self.llm.invoke(qa_prompt).content.strip()
        response_text = redact_pii(response_text)
        response_text = self._enforce_sentence_limit(response_text, max_sentences=3)

        # Clear sources if the LLM gave a generic/conversational reply instead of a factual one
        _generic_markers = ("verified source for that", "how can i assist", "happy to help",
                            "please go ahead", "go ahead and ask", "what would you like",
                            "how can i help", "feel free to ask")
        if any(m in response_text.lower() for m in _generic_markers):
            sources = []

        return Answer(
            text=response_text,
            citation_links=sources
        )


@lru_cache(maxsize=1)
def get_rag_engine() -> RAGEngine:
    """Returns a shared, lazily-initialised RAGEngine instance.

    Loading the embedding model, vector store, and LLM client is expensive
    (multiple seconds), so it must happen once per process rather than on
    every request.
    """
    return RAGEngine()
