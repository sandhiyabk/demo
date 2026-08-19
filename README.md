# PrepGym AI — Adaptive Interview Gym

An AI-powered interview practice dashboard that simulates a real interviewer,
evaluates answers with structured, actionable feedback, and generates a
targeted revision plan based on session history.

**Live Demo:** https://jfywvpggunwqe7yd2zfmvz.streamlit.app/

## Problem

Students practice interview questions but get no consistent evaluation of
*where* they're weak — fundamentals, depth, or communication — and no clear
path from a raw score to an improvement plan.

## Architecture

```
[1. SIMULATION LOOP] ──────► [2. STRUCTURED EVALUATOR] ──────► [3. ADAPTIVE TRACKER]
Conversation-aware question   Strict JSON scorecard via Groq    Aggregates session history
generation, one Q at a time   JSON mode (temp=0.2)              into a 3-part sprint plan
```

Three deliberately separate prompts (`prompts.py`):
1. **Question generation** — aware of prior Q&A, asks natural follow-ups
2. **Answer evaluation** — deterministic JSON: score, strengths, weaknesses,
   missing concepts, improved answer
3. **Sprint plan** — turns accumulated weak topics into a revision roadmap

Each prompt has a single job and a strict output contract, so any one stage
can be debugged or improved without breaking the others.

## Stack

- **Streamlit** — single-process UI, no separate API server (deliberate
  scope cut for a 5-hour build — same architecture, less plumbing)
- **Groq API** (`openai/gpt-oss-120b`), native JSON mode, temp=0.2
- **SQLite + SQLAlchemy** — persists every attempt across refreshes

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add your GROQ_API_KEY
streamlit run app.py
```

## Scope decisions (for the video)

- **2 tracks (DSA, SQL)** instead of 5 — deeper polish per track beats
  shallow coverage of five, in six hours.
- **No auth / multi-user** — one active session, matches the brief.
- **JSON-mode with retry-then-error** instead of silent failure — if Groq
  returns malformed JSON twice, the UI shows a clean error instead of
  crashing.

## Known AI failure mode (documented, not hidden)

The evaluator can be overly generous on partially-correct answers that use
confident language. Mitigated by explicitly instructing the model to
*justify the score before committing to it* in the system prompt — this
measurably tightened scoring on ambiguous answers during testing.
