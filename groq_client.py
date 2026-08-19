"""
Groq API wrapper.
- Uses native JSON mode (response_format={"type": "json_object"})
- temperature=0.2 for deterministic-ish structured output
- Retries once on malformed JSON / API error before raising
"""
import os
import json
import time
import streamlit as st
from groq import Groq

MODEL = "openai/gpt-oss-120b"

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Add it to your .env file or environment."
            )
        _client = Groq(api_key=api_key)
    return _client


def call_groq_json(system_prompt: str, user_prompt: str,
                    temperature: float = 0.2, max_retries: int = 2) -> dict:
    """
    Calls Groq with JSON mode. Retries on parse/API failure.
    Raises RuntimeError with the last error if all retries fail,
    so the caller can show a clean UI error instead of crashing.
    """
    client = get_client()
    last_err = None

    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = resp.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError as e:
            last_err = f"Malformed JSON from model: {e}"
        except Exception as e:
            last_err = f"Groq API error: {e}"

        # Surface retry to the user so a silent delay isn't confusing.
        if attempt < max_retries:
            st.warning(f"API issue detected, retrying ({attempt + 1}/{max_retries})...")
        time.sleep(0.6)

    raise RuntimeError(f"Groq call failed after {max_retries + 1} attempts: {last_err}")
