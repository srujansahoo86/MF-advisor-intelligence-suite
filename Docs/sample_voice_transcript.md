# Sample Voice Transcript — FINTELLIGENCE Voice Scheduler

This transcript shows a complete multi-turn session with the Phase 3 voice booking agent.
The Weekly Pulse top theme for this session is **"Exit Load Awareness"** (injected from Phase 2).

---

## Session 1 — New Booking

**User:** Hi, I'd like to book an appointment with an advisor.

**Agent:** Many users are asking about Exit Load Awareness this week — I can book a slot for that!
Here are the available appointment slots:
- Monday 10:00 AM
- Monday 2:00 PM
- Tuesday 10:00 AM
- Tuesday 3:00 PM
- Wednesday 11:00 AM
- Wednesday 4:00 PM
- Thursday 9:00 AM
- Thursday 2:00 PM
- Friday 10:00 AM
- Friday 3:00 PM

Which one works for you?

**User:** Monday morning works for me.

**Agent:** Many users are asking about Exit Load Awareness this week — I can book a slot for that!
Your appointment is confirmed for Monday 10:00 AM. Your Booking Code is **KV-M3A2**.
Please save it — you'll need it to reschedule or cancel.

> **MCP actions queued (PENDING — awaiting advisor approval):**
> 1. Calendar Hold Creator — Monday 10:00 AM, 30 min, attendees: advisor@kuvera.in
> 2. Doc Append — logs booking summary to `data/shared_notes.md`
> 3. Email Draft Generator — pre-meeting brief on "Exit Load Awareness" for advisor@kuvera.in

---

## Session 2 — Preparation Help

**User:** What should I prepare for my call?

**Agent:** To prepare for your call, please have your investment goals and any existing portfolio statements ready.

Here is some information about Exit Load Awareness:
Exit loads are fees charged when you redeem mutual fund units before a specified holding period. For Parag Parikh Liquid Fund, the exit load is Nil (no exit load applies). For ELSS funds on Kuvera, a mandatory 3-year lock-in applies, after which no exit load is charged. Always check the Key Information Memorandum (KIM) for the specific exit load schedule of any fund before investing.
[Source: amc.ppfas.com — KIM Parag Parikh Liquid Fund](https://amc.ppfas.com/downloads/parag-parikh-liquid-fund/kim-parag-parikh-liquid-fund.pdf?21052026)

---

## Session 3 — Reschedule

**User:** I need to reschedule my booking KV-M3A2.

**Agent:** Here are the available appointment slots:
- Monday 2:00 PM
- Tuesday 10:00 AM
- Tuesday 3:00 PM
- Wednesday 11:00 AM
- Wednesday 4:00 PM
- Thursday 9:00 AM
- Thursday 2:00 PM
- Friday 10:00 AM
- Friday 3:00 PM

Which one would you like to move your appointment to?

**User:** Tuesday at 3 PM please.

**Agent:** Your appointment has been rescheduled. Old booking KV-M3A2 is cancelled. Your new appointment is confirmed for Tuesday 3:00 PM. Your new Booking Code is **KV-7BQF**.

> **MCP actions queued (PENDING):**
> 1. Calendar Hold Creator — Tuesday 3:00 PM
> 2. Doc Append — updated booking log
> 3. Email Draft Generator — revised pre-meeting brief

---

## Session 4 — PII Deflection

**User:** My PAN is ABCDE1234F, can you use that to look up my account?

**Agent:** For security, please do not share personal details here. To access your account information securely, please visit: https://kuvera.in/secure-profile

---

## Session 5 — Out-of-Scope Request

**User:** Which fund should I invest in right now?

**Agent:** I can help you book, reschedule, or prepare for advisor appointments. For other questions, please consult our FAQ chatbot.

---

## Session 6 — Session End

**User:** That's all, goodbye.

**Agent:** Thank you for calling Kuvera. Have a great day!

---

## Notes

- Booking codes follow the format `KV-XXXX` (4 alphanumeric characters).
- All MCP tool actions (Calendar Hold, Doc Append, Email Draft) are queued as `PENDING` and only execute after the advisor approves them via the Approval Centre.
- The Weekly Pulse top theme is read from `latest_pulse` in SQLite and injected into every booking greeting automatically.
- PII (PAN numbers, phone numbers, email addresses) is detected and deflected to `https://kuvera.in/secure-profile` before any LLM processing.
