"""
PrepGym AI — Adaptive Interview Gym
Run with: streamlit run app.py
"""
import streamlit as st
import datetime
import pandas as pd
from dotenv import load_dotenv

from db import init_db, save_attempt, get_all_attempts, get_weak_attempts, get_topic_score_stats
from groq_client import call_groq_json
from prompts import (
    TRACKS,
    QUESTION_SYSTEM, build_question_prompt,
    EVALUATE_SYSTEM, build_evaluate_prompt,
    SPRINT_SYSTEM, build_sprint_prompt,
)

load_dotenv()
init_db()

st.set_page_config(page_title="PrepGym AI", page_icon="🎯", layout="wide")

# ---------- session state ----------
# Persists across Streamlit reruns within one browser session.
defaults = {
    "track": None,
    "current_question": None,   # {"question", "topic", "difficulty"}
    "asked_topics": [],
    "last_qa": None,            # {"question", "answer"} for follow-up context
    "evaluation": None,
    "session_count": 0,
    "session_start": None,
    "session_scores": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def fetch_question(track, retry_question=None):
    """Get a new question from Groq. If retry_question is passed, re-ask it without an API call."""
    if retry_question:
        st.session_state.current_question = {
            "question": retry_question, "topic": "retry", "difficulty": "n/a"
        }
        return
    prompt = build_question_prompt(track, st.session_state.asked_topics, st.session_state.last_qa)
    # Streamlit spinners show a loading indicator while the Groq call completes.
    with st.spinner("Interviewer is thinking..."):
        q = call_groq_json(QUESTION_SYSTEM, prompt)
    st.session_state.current_question = q
    st.session_state.evaluation = None  # clear previous scorecard


def evaluate_answer(track, question, answer):
    prompt = build_evaluate_prompt(track, question, answer)
    with st.spinner("Evaluating your answer..."):
        result = call_groq_json(EVALUATE_SYSTEM, prompt)
    return result


# ---------- SIDEBAR: track selection + dashboard ----------
with st.sidebar:
    st.title("🎯 PrepGym AI")
    st.caption("Adaptive Interview Gym")

    track = st.selectbox("Choose your track", TRACKS)
    if st.button("Start / Restart Session", use_container_width=True):
        # Reset all session-specific state for a clean start.
        st.session_state.track = track
        st.session_state.asked_topics = []
        st.session_state.last_qa = None
        st.session_state.evaluation = None
        st.session_state.session_start = datetime.datetime.now()
        st.session_state.session_scores = []
        fetch_question(track)
        st.rerun()

    st.divider()
    st.subheader("📊 Your Progress")
    attempts = get_all_attempts()
    if attempts:
        avg = sum(a["score"] for a in attempts) / len(attempts)
        st.metric("Attempts", len(attempts))
        st.metric("Average score", f"{avg:.1f}/10")

        weak = get_weak_attempts()
        if weak:
            st.markdown("**Weak topics:**")
            for w in weak[-5:]:
                st.write(f"- {w['topic']} ({w['score']}/10)")

        if st.button("🧭 Generate Sprint Plan", use_container_width=True):
            history = [
                {"track": a["track"], "topic": a["topic"], "score": a["score"], "weaknesses": a["weaknesses"]}
                for a in attempts
            ]
            with st.spinner("Building your revision plan..."):
                try:
                    plan = call_groq_json(SPRINT_SYSTEM, build_sprint_prompt(history))
                    st.session_state.sprint_plan = plan
                except RuntimeError as e:
                    st.error(f"Couldn't generate plan: {e}")
    else:
        st.info("No attempts yet. Start a session!")

    if st.session_state.get("sprint_plan"):
        st.divider()
        st.subheader("🗺️ Sprint Plan")
        plan = st.session_state.sprint_plan

        # Build topic-to-avg-score mapping for the bar chart.
        # "attempts" is always defined above (line 79) — safe to use here.
        topic_scores = {}
        for a in attempts:
            topic_scores.setdefault(a["topic"], []).append(a["score"])
        if topic_scores:
            df = pd.DataFrame([
                {"Topic": t, "Avg Score": sum(s) / len(s)}
                for t, s in topic_scores.items()
            ]).sort_values("Avg Score")
            st.bar_chart(df, x="Topic", y="Avg Score", horizontal=True, height=150 + 30 * len(df))

        st.write("**Recommended exercises:**")
        for e in plan.get("recommended_exercises", []):
            st.write(f"- {e}")
        st.info(plan.get("next_focus", ""))


# ---------- MAIN: interview screen ----------
st.header("Interview Session")

if not st.session_state.track:
    st.info("👈 Pick a track and click **Start Session** to begin.")
else:
    if not st.session_state.current_question:
        try:
            fetch_question(st.session_state.track)
        except RuntimeError as e:
            st.error(str(e))
            st.stop()

    q = st.session_state.current_question
    st.subheader(f"Track: {st.session_state.track}  |  Topic: {q.get('topic', '—')}  |  {q.get('difficulty', '')}")
    st.markdown(f"**Q: {q['question']}**")

    answer = st.text_area("Your answer", height=150, key=f"answer_{q['question'][:20]}")
    code_answer = st.text_area("Code (optional)", height=100, key=f"code_{q['question'][:20]}")

    full_answer = answer + ("\n\n```\n" + code_answer + "\n```" if code_answer.strip() else "")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Submit Answer", type="primary", use_container_width=True):
            if not answer.strip():
                st.warning("Please write an answer first.")
            # Reject very short answers — saves a Groq API call for low-value input.
            elif len(answer.strip()) < 10:
                st.warning("Answer too short — write at least a sentence so the evaluation is meaningful.")
            else:
                try:
                    # Send to Groq evaluator and persist the result in SQLite.
                    result = evaluate_answer(st.session_state.track, q["question"], full_answer)
                    st.session_state.evaluation = result
                    save_attempt(st.session_state.track, q.get("topic", "general"),
                                 q["question"], full_answer, result)
                    # Track what we've covered so the next question is a follow-up.
                    st.session_state.asked_topics.append(q.get("topic", "general"))
                    st.session_state.last_qa = {"question": q["question"], "answer": full_answer}
                    st.session_state.session_count += 1
                    st.session_state.session_scores.append(result.get("score", 0))
                except RuntimeError as e:
                    st.error(f"Evaluation failed: {e}")

    # ---------- scorecard ----------
    # Only renders after a successful evaluation. Uses .get() for safe
    # access — a malformed Groq response may omit expected keys.
    if st.session_state.evaluation:
        ev = st.session_state.evaluation
        st.divider()
        # Safe fallback: a malformed-but-JSON-valid Groq response may omit "score".
        score = ev.get("score", 0)
        st.subheader(f"Score: {score}/10")

        # Show inconsistency badge when a topic has high score variance across attempts.
        topic = q.get("topic", "general")
        stats = get_topic_score_stats(st.session_state.track, topic)
        if stats["stddev"] >= 2.0 and stats["count"] >= 3:
            st.markdown(
                '<span style="background:#ff6b6b;color:white;padding:2px 8px;'
                'border-radius:10px;font-size:0.8em;">⚠️ Inconsistent on this topic '
                f'(σ={stats["stddev"]:.1f}, {stats["count"]} attempts)</span>',
                unsafe_allow_html=True,
            )

        st.progress(min(score, 10) / 10)

        st.write(f"**Correctness:** {ev['correctness']}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("✅ **Strengths**")
            for s in ev.get("strengths", []):
                st.write(f"- {s}")
        with c2:
            st.markdown("⚠️ **Weaknesses**")
            for w in ev.get("weaknesses", []):
                st.write(f"- {w}")

        if ev.get("missing_concepts"):
            st.markdown("❌ **Missing concepts**")
            for m in ev["missing_concepts"]:
                st.write(f"- {m}")

        with st.expander("✨ Improved model answer"):
            st.write(ev.get("improved_answer", ""))

        col3, col4 = st.columns(2)
        with col3:
            if st.button("Next Question →", use_container_width=True):
                fetch_question(st.session_state.track)
                st.rerun()
        with col4:
            if st.button("🔁 Retry this question", use_container_width=True):
                fetch_question(st.session_state.track, retry_question=q["question"])
                st.session_state.evaluation = None
                st.rerun()

# ---------- session summary ----------
# Only render if a session is active (start button was clicked at least once).
if st.session_state.track and st.session_state.session_scores and st.session_state.session_start:
    st.divider()
    with st.expander("📋 Session Summary"):
        elapsed = datetime.datetime.now() - st.session_state.session_start
        mins, secs = divmod(int(elapsed.total_seconds()), 60)
        c1, c2 = st.columns(2)
        c1.metric("Questions this session", len(st.session_state.session_scores))
        c1.metric("Session time", f"{mins}m {secs}s")
        c2.metric("Session avg", f"{sum(st.session_state.session_scores)/len(st.session_state.session_scores):.1f}/10")
        trend_df = pd.DataFrame({
            "Question #": list(range(1, len(st.session_state.session_scores) + 1)),
            "Score": st.session_state.session_scores,
        })
        st.line_chart(trend_df, x="Question #", y="Score", height=200)
