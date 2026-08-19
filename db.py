"""
SQLite persistence via SQLAlchemy.
One table: attempts — every answered question + its evaluation.
"""
import json
import math
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = "sqlite:///prepgym.db"
engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_label = Column(String, default="default")
    track = Column(String)
    topic = Column(String)
    question = Column(Text)
    answer = Column(Text)
    score = Column(Float)
    correctness = Column(Text)
    strengths = Column(Text)       # JSON-encoded list
    weaknesses = Column(Text)      # JSON-encoded list
    missing_concepts = Column(Text)  # JSON-encoded list
    improved_answer = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)


def save_attempt(track, topic, question, answer, evaluation: dict):
    db = SessionLocal()
    try:
        row = Attempt(
            track=track,
            topic=topic,
            question=question,
            answer=answer,
            score=evaluation.get("score", 0),
            correctness=evaluation.get("correctness", ""),
            strengths=json.dumps(evaluation.get("strengths", [])),
            weaknesses=json.dumps(evaluation.get("weaknesses", [])),
            missing_concepts=json.dumps(evaluation.get("missing_concepts", [])),
            improved_answer=evaluation.get("improved_answer", ""),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def get_all_attempts():
    db = SessionLocal()
    try:
        rows = db.query(Attempt).order_by(Attempt.created_at.asc()).all()
        result = []
        for r in rows:
            result.append({
                "id": r.id,
                "track": r.track,
                "topic": r.topic,
                "question": r.question,
                "answer": r.answer,
                "score": r.score,
                "weaknesses": json.loads(r.weaknesses or "[]"),
                "created_at": r.created_at,
            })
        return result
    finally:
        db.close()


def get_weak_attempts(threshold: float = 6.0):
    return [a for a in get_all_attempts() if a["score"] < threshold]


def get_topic_score_stats(track: str, topic: str):
    """Return mean, stddev, and count of scores for a given track+topic."""
    attempts = [a for a in get_all_attempts() if a["track"] == track and a["topic"] == topic]
    scores = [a["score"] for a in attempts]
    n = len(scores)
    if n < 2:
        return {"mean": scores[0] if scores else 0, "stddev": 0.0, "count": n}
    mean = sum(scores) / n
    variance = sum((s - mean) ** 2 for s in scores) / n
    return {"mean": mean, "stddev": math.sqrt(variance), "count": n}
