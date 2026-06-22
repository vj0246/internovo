import os
import json
import asyncio
import httpx
from config import GROQ_MODEL, GROQ_API_URL, PEOPLE, CONFIDENCE_THRESHOLD

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


async def _call_groq(messages: list, temperature: float = 0.0) -> str:
    """3-attempt exponential-backoff retry: 0.5 s → 1 s → raise."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set.")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": GROQ_MODEL, "messages": messages, "temperature": temperature}
    last_err = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(GROQ_API_URL, headers=headers, json=payload)
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            last_err = exc
            if attempt < 2:
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise last_err


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


async def check_vague(question: str, answer: str) -> dict:
    """Returns {"vague": bool, "reason": str}"""
    system = (
        "You assess whether a user's answer to a design intake question is too vague.\n\n"
        "MARK vague=false for: any specific design type, clear purpose, any deadline (even rough), "
        "any budget amount, any brand reference including 'no guidelines yet'.\n\n"
        "MARK vague=true ONLY for: completely empty, pure non-answers "
        "('yes', 'no', 'idk', 'maybe', 'something', 'stuff').\n\n"
        'Reply ONLY with JSON: {"vague": true/false, "reason": "short reason"}'
    )
    raw = await _call_groq([
        {"role": "system", "content": system},
        {"role": "user",   "content": f"Question: {question}\nAnswer: {answer}"},
    ])
    try:
        return json.loads(_strip_fence(raw))
    except Exception:
        return {"vague": False, "reason": ""}


async def extract_preanswers(original_query: str, questions: list) -> list:
    """Check which questions the initial query already answers. Conservative."""
    numbered = "\n".join(f"{i}. {q}" for i, q in enumerate(questions))
    system = (
        "A design client submitted an initial request. For each question below, "
        "decide if the request EXPLICITLY answers it (not loosely guessable). "
        "Extract a short phrase if answered.\n"
        'Reply ONLY with JSON array: [{"answered": true/false, "answer": "..." or null}, ...]'
    )
    raw = await _call_groq([
        {"role": "system", "content": system},
        {"role": "user",   "content": f"Request: {original_query}\n\nQuestions:\n{numbered}"},
    ])
    try:
        result = json.loads(_strip_fence(raw))
        if isinstance(result, list) and len(result) == len(questions):
            return result
    except Exception:
        pass
    return [{"answered": False, "answer": None} for _ in questions]


async def route_query(original_query: str, qa_pairs: list) -> dict:
    """
    Returns {"matches": [{"name", "role", "confidence", "reason"}, ...]}
    Every person in the result has a reason — no empty strings.
    """
    people_desc = "\n".join(
        f"- {p['name']} ({p['role']}): {p['description']}" for p in PEOPLE
    )
    qa_text = "\n".join(f"Q: {qa['question']}\nA: {qa['answer']}" for qa in qa_pairs)

    system = (
        "You are a design request router. Score EVERY person below (0-100) on domain match.\n\n"
        "RULES:\n"
        "- Score >50 only for genuine domain match\n"
        "- Multiple people can score >50 if request spans domains\n"
        "- You MUST write a `reason` for EVERY person — a single specific sentence "
        "  explaining exactly why this request does or doesn't match their domain. "
        "  Never leave reason empty or generic.\n\n"
        "Reply ONLY with a JSON array, no prose, no markdown:\n"
        '[{"name": "...", "confidence": 0-100, "reason": "specific sentence"}, ...]\n'
        "Include ALL people.\n\n"
        f"People:\n{people_desc}"
    )
    raw = await _call_groq([
        {"role": "system", "content": system},
        {"role": "user",   "content": f"Request: {original_query}\n\n{qa_text}"},
    ])
    try:
        scores = json.loads(_strip_fence(raw))
    except Exception:
        scores = []

    person_map = {p["name"]: p["role"] for p in PEOPLE}

    def _ensure_reason(s: dict) -> str:
        """Guarantee a non-empty reason."""
        r = (s.get("reason") or "").strip()
        if r:
            return r
        conf = s.get("confidence", 0)
        name = s.get("name", "")
        if conf >= 70:
            return f"Strong domain alignment — {name}'s expertise closely matches this request."
        if conf >= CONFIDENCE_THRESHOLD:
            return f"Partial match — some overlap with {name}'s domain."
        return f"Low relevance — this request falls outside {name}'s primary domain."

    matches = [
        {
            "name":       s["name"],
            "role":       person_map.get(s["name"], ""),
            "confidence": s["confidence"],
            "reason":     _ensure_reason(s),
        }
        for s in scores
        if isinstance(s, dict) and s.get("confidence", 0) >= CONFIDENCE_THRESHOLD
    ]
    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return {"matches": matches}
