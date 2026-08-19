"""
Three separate, single-purpose prompts (the core architectural decision
to highlight in the video):
  1. Question generation  — conversation-aware, one question at a time
  2. Answer evaluation     — strict JSON scorecard
  3. Sprint plan           — turns session history into a revision plan
"""

TRACKS = ["DSA", "SQL"]

# ---------- 1. QUESTION GENERATION ----------

QUESTION_SYSTEM = """You are an experienced technical interviewer at a top product company.
You ask ONE question at a time, the way a real interviewer would.
If given the candidate's previous answer, your next question should be a natural,
contextual follow-up that probes deeper into a weak or vague part of that answer.
If there is no previous answer, ask a solid opening question for the given track.

Always respond with ONLY a JSON object, no extra text, in this exact shape:
{
  "question": "the question text",
  "topic": "short topic tag, e.g. 'Arrays', 'Joins', 'Time Complexity'",
  "difficulty": "easy" | "medium" | "hard"
}
"""


def build_question_prompt(track: str, asked_topics: list[str], last_qa: dict | None) -> str:
    parts = [f"Track: {track}"]
    if asked_topics:
        parts.append(f"Topics already covered this session: {', '.join(asked_topics)}")
    else:
        parts.append("This is the first question of the session.")

    if last_qa:
        parts.append(f"Previous question: {last_qa['question']}")
        parts.append(f"Candidate's answer: {last_qa['answer']}")
        parts.append(
            "Generate a contextual follow-up question that drills into a gap "
            "or vague assumption in that answer. Avoid repeating covered topics "
            "unless testing depth."
        )
    else:
        parts.append("Generate a solid opening question for this track, easy-to-medium difficulty.")

    return "\n".join(parts)


# ---------- 2. ANSWER EVALUATION ----------

EVALUATE_SYSTEM = """You are a strict but fair technical interview evaluator.
Evaluate the candidate's answer on: correctness, clarity, depth, complexity analysis
(if relevant), and communication.
Be specific and honest — do not inflate scores. Justify the score before committing to it.

Always respond with ONLY a JSON object, no extra text, in this exact shape:
{
  "score": <integer 0-10>,
  "correctness": "one or two sentences on technical correctness",
  "strengths": ["short bullet", "short bullet"],
  "weaknesses": ["short bullet", "short bullet"],
  "missing_concepts": ["concept the candidate should have mentioned"],
  "follow_up_question": "a natural next question probing the weakest point",
  "improved_answer": "a concise, interview-quality model answer"
}
"""


def build_evaluate_prompt(track: str, question: str, answer: str) -> str:
    return (
        f"Track: {track}\n"
        f"Question: {question}\n"
        f"Candidate's answer: {answer}\n\n"
        "Evaluate this answer now."
    )


# ---------- 3. SPRINT PLAN ----------

SPRINT_SYSTEM = """You are a technical interview coach reviewing a student's practice session.
Based on their attempt history (topics, scores, weaknesses), produce a short,
realistic revision plan they can act on before their next interview.

Always respond with ONLY a JSON object, no extra text, in this exact shape:
{
  "priority_topics": ["topic ranked by weakness", "..."],
  "recommended_exercises": ["concrete, specific exercise", "..."],
  "next_focus": "one sentence: what to focus on in the very next practice session"
}
"""


def build_sprint_prompt(history: list[dict]) -> str:
    lines = ["Session history (most recent last):"]
    for h in history:
        lines.append(
            f"- Track: {h['track']} | Topic: {h['topic']} | Score: {h['score']}/10 "
            f"| Weaknesses: {', '.join(h['weaknesses']) if h['weaknesses'] else 'none noted'}"
        )
    lines.append("\nGenerate the revision plan now.")
    return "\n".join(lines)
