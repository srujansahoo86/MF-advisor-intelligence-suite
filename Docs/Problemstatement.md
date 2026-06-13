Mutual Fund Advisor Intelligence Suite
Objective
Build a voice-first AI mutual fund support assistant that can answer factual scheme queries, analyze customer feedback to generate actionable product insights, book advisor appointments via voice, and connect all three into a single unified dashboard.
This capstone is designed to test whether you can design, build, and evaluate a real GenAI system — not just a prompt-based demo.
Problem Statement
People don't struggle to find mutual fund schemes. They struggle to understand what they're actually invested in, why they were charged a fee, and who to call when they're confused.
Your task is to build an integrated AI assistant that:
•	Answers factual questions about mutual fund schemes using verified, cited sources
•	Analyses real user reviews to surface recurring pain points and generate a weekly product pulse
•	Books advisor appointments via voice, using live review insights to brief the advisor
•	Connects all three capabilities into one dashboard with a human-in-the-loop approval layer
Along with the above, implement an MCP workflow that logs outputs to a shared document and drafts a pre-meeting advisor email — approval-gated before anything is sent.
What You Will Build
A deployed mutual fund support dashboard with three connected AI pillars and a minimal companion UI.
Core Capabilities (Required)
1. FAQ Chatbot — Facts-Only Q&A (Milestone 1)
The assistant must answer factual scheme queries such as:
•	"What is the exit load for the ELSS fund on Kuvera?"
•	"What is the minimum SIP amount for the Parag Parikh Flexi Cap Fund?"
•	"How do I download my capital gains statement?"
Rules:
•	Every answer must include one source citation link.
•	Ask clarifying questions only when the scheme is ambiguous (max 3).
•	Refuse investment advice with a polite message and an AMFI educational link.
•	Answers must be ≤ 3 sentences. No performance claims. No PII collected.
2. Review Intelligence & Weekly Pulse (Milestone 2)
The system must process a raw reviews CSV and produce two structured outputs:
•	Weekly Product Pulse (≤ 250 words): top themes, user quotes, key observation, 3 action ideas for the product team.
•	Fee Explainer: a 6-bullet plain-language explanation of the most-confused fee, with 2 official source links and a Last checked: date.
The Fee Explainer output must be appended to the FAQ chatbot's retrieval corpus so this week's confusion improves next week's answers.
3. Voice Appointment Scheduler (Milestone 3)
The user must be able to book an advisor slot via voice:
•	"I want to book a call about my SIP mandate."
•	"Can I reschedule my appointment to Friday afternoon?"
•	"What should I prepare for my call?"
On confirmation:
•	Generate a Booking Code (e.g., KV-B391) and read it aloud.
•	The voice agent greeting must dynamically reference the top theme from the current week's Pulse (e.g., "Many users are asking about exit load confusion this week — I can book a slot for that!").
•	No PII on the call. If the user volunteers personal details, deflect to the secure link.
Companion UI
Your UI can be simple, but must include:
•	Three clearly labelled pillar views: FAQ, Weekly Pulse, Voice Scheduler
•	FAQ view: answer display with citation link and source badge
•	Pulse view: top themes, user quotes, fee explainer, action ideas
•	Scheduler view: microphone button, live transcript, booking confirmation with Booking Code
•	An Approval Centre showing pending MCP actions (Calendar Hold / Notes Entry / Email Draft) with approve / reject controls
•	A Sources section listing the official URLs used by the RAG engine
Data Requirements
You must use publicly available, official sources only.
Required:
•	AMC factsheets and KIM/SID pages (for scheme facts)
•	AMFI / SEBI public pages (for regulatory and fee data)
•	Kuvera public documentation (for platform-specific guidance)
•	A reviews CSV (simulated or scraped, minimum 30–50 reviews, last 8–12 weeks)
Rules:
•	Every FAQ answer must trace back to a source in your corpus
•	The Fee Explainer must cite 2 official URLs
•	If data is missing, the system must say so explicitly — no hallucinated facts
•	Minimum 30 URLs across your full source manifest
MCP Integration
Your system must use at least three MCP tools in the orchestration layer.
Required MCP Tools:
ToolInputsOutputsNotes / Doc Appenddate, top themes, pulse, fee explainer, booking codeAppended entry in shared docCalendar Hold Creatortopic, slot, booking codeTentative calendar hold with code in titleEmail Draft Generatoradvisor details, pulse snippet, booking codeDraft email with market context — no auto-send
Optional MCP Tools (Bonus):
•	Slack / Teams notification MCP
•	Review ingestion automation MCP
All MCP actions must pass through a visible human-approval step before execution. You must demonstrate MCP calls clearly in your demo.
RAG Requirements
RAG must be used for:
•	Scheme facts (expense ratio, exit load, lock-in, benchmark, riskometer)
•	Fee explanations derived from review confusion
•	Advisor email market context snippets
Rules:
•	All factual answers must include a citation link
•	No hallucinated claims — if the corpus doesn't contain the answer, say so
•	Voice responses can be short; citations must appear in the UI
•	The Fee Explainer generated by M2 must be retrievable by the M1 FAQ engine (show the refresh mechanism)
AI Evaluations
You must implement at least three evaluation checks:
1. Retrieval Accuracy Eval (RAG Eval)
•	Create a Golden Dataset of 5 questions requiring both scheme facts (M1) and fee logic (M2)
•	Measure: Faithfulness (≥ 0.8), Relevance (≥ 0.8), Citation Accuracy (Pass/Fail)
2. Compliance & Safety Eval (Adversarial Eval)
•	Test with 5 adversarial prompts: investment advice requests, PII extraction attempts, out-of-scope escalations
•	Metric: Pass/Fail — system must refuse correctly 5/5 times
•	Document any failures and what you changed to fix them
3. Tone & Structure Eval (UX Eval)
•	Weekly Pulse: ≤ 250 words, exactly 3 action ideas, at least 1 user quote, no PII
•	Fee Explainer: exactly 6 bullets, neutral tone, 2 source links, Last checked: stamp
•	Voice Agent: Top Theme appears in greeting (Pass/Fail), Booking Code in Notes/Doc (Pass/Fail), Market Context in email draft (Pass/Fail)
Evals can be rule-based or LLM-assisted but must be runnable and documented.
Tech & Deployment Requirements
•	Build using LLM APIs
•	Voice input (speech-to-text required for the scheduler pillar)
•	Version control using git
•	Deployed prototype (public URL)
•	Single UI entry point — all three pillars accessible from one app

