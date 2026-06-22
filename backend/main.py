import uuid
import asyncio
from typing import Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, update, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config import FIXED_QUESTIONS, PEOPLE
from llm import check_vague, route_query, extract_preanswers
from database import DBBrief, DBAnswer, DBMatch, init_db, get_db

# ── In-memory store (active conversations only) ───────────────────────────────
SESSIONS: dict = {}
SESSION_TTL_HOURS = 2

EXAMPLE_HINTS = {
    0: "e.g. 'A logo for my startup' or 'Social media posts for a launch'",
    1: "e.g. 'For an investor pitch' or 'For a new product launch campaign'",
    2: "e.g. 'By next Friday' or 'Within 2 weeks'",
    3: "e.g. 'No guidelines yet' or 'We use blue and white, I have a moodboard'",
    4: "e.g. '$500–$1,000' or 'Flexible, under $2k'",
}


def new_session(query: str) -> dict:
    return {
        "original_query": query,
        "answers":        [None] * len(FIXED_QUESTIONS),
        "completed":      [False] * len(FIXED_QUESTIONS),
        "routed":         False,
        "created_at":     datetime.utcnow(),
    }


def next_unanswered(session: dict) -> Optional[int]:
    for i, done in enumerate(session["completed"]):
        if not done:
            return i
    return None


def routing_message(matches: list) -> str:
    if not matches:
        return "No clear match found. Someone from the team will be assigned shortly."
    parts  = [f"{m['name']} ({m['role']})" for m in matches]
    joined = " and ".join(parts) if len(parts) <= 2 else ", ".join(parts[:-1]) + f" and {parts[-1]}"
    return f"Your brief has been routed to {joined}. You'll hear back shortly."


def brief_to_dict(b: DBBrief) -> dict:
    return {
        "session_id":     b.id,
        "original_query": b.original_query,
        "created_at":     b.created_at.isoformat() if b.created_at else None,
        "completed":      b.completed,
        "routed":         b.routed,
        "routed_at":      b.routed_at.isoformat() if b.routed_at else None,
        "qa_pairs": [
            {"index": a.question_index, "question": a.question_text, "answer": a.answer_text}
            for a in sorted(b.answers, key=lambda x: x.question_index)
        ],
        "matches": [
            {"name": m.person_name, "role": m.person_role or "",
             "confidence": m.confidence, "reason": m.reason or ""}
            for m in sorted(b.matches, key=lambda x: x.confidence, reverse=True)
        ],
    }


# ── Multi-answer extraction ───────────────────────────────────────────────────
async def _try_fill_from_answer(
    sid: str, session: dict, source_answer: str, db: AsyncSession
) -> None:
    """
    After accepting an answer for one question, check if that same answer
    also contains answers to other still-pending questions and fill them in.

    Example: user answers Q2 with
      "purpose is product launch, deadline is 25 June, brand refs are blue background"
    → this also fills Q3 (deadline) and Q4 (brand refs) automatically.
    """
    remaining = [
        (i, FIXED_QUESTIONS[i])
        for i, done in enumerate(session["completed"])
        if not done
    ]
    if not remaining:
        return

    remaining_qs = [q for _, q in remaining]
    preanswers   = await extract_preanswers(source_answer, remaining_qs)

    filled = False
    for j, pa in enumerate(preanswers):
        if not pa.get("answered") or not pa.get("answer"):
            continue
        candidate = str(pa["answer"]).strip()
        if not candidate:
            continue
        orig_idx = remaining[j][0]
        verdict  = await check_vague(FIXED_QUESTIONS[orig_idx], candidate)
        if verdict.get("vague"):
            continue
        session["answers"][orig_idx]   = {"question": FIXED_QUESTIONS[orig_idx], "answer": candidate}
        session["completed"][orig_idx] = True
        db.add(DBAnswer(
            brief_id=sid, question_index=orig_idx,
            question_text=FIXED_QUESTIONS[orig_idx], answer_text=candidate,
        ))
        filled = True

    if filled:
        await db.execute(
            update(DBBrief).where(DBBrief.id == sid)
            .values(completed=session["completed"])
        )
        await db.commit()


# ── Cleanup loop ──────────────────────────────────────────────────────────────
async def _cleanup_loop():
    while True:
        await asyncio.sleep(1800)
        cutoff  = datetime.utcnow() - timedelta(hours=SESSION_TTL_HOURS)
        expired = [sid for sid, s in list(SESSIONS.items()) if s["created_at"] < cutoff]
        for sid in expired:
            SESSIONS.pop(sid, None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://internovo.vercel.app", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────────────
class StartRequest(BaseModel):
    query: str

class StartResponse(BaseModel):
    session_id:      str
    status:          str
    message:         Optional[str] = None
    question:        Optional[str] = None
    question_index:  Optional[int] = None
    total_questions: int
    completed:       Optional[list] = None
    matches:         Optional[list] = None

class AnswerRequest(BaseModel):
    session_id: str
    answer:     str

class AnswerResponse(BaseModel):
    status:         str
    message:        str
    question:       Optional[str] = None
    question_index: Optional[int] = None
    completed:      Optional[list] = None
    matches:        Optional[list] = None


# ── /start ────────────────────────────────────────────────────────────────────
@app.post("/start", response_model=StartResponse)
async def start(req: StartRequest, db: AsyncSession = Depends(get_db)):
    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty.")
    query = req.query.strip()
    sid   = str(uuid.uuid4())

    db.add(DBBrief(id=sid, original_query=query, completed=[False] * 5))
    await db.commit()

    session = new_session(query)
    SESSIONS[sid] = session

    # Pre-fill from initial query
    preanswers = await extract_preanswers(query, FIXED_QUESTIONS)
    for i, qa in enumerate(preanswers):
        if not qa.get("answered") or not qa.get("answer"):
            continue
        candidate = str(qa["answer"]).strip()
        if not candidate:
            continue
        verdict = await check_vague(FIXED_QUESTIONS[i], candidate)
        if verdict.get("vague"):
            continue
        session["answers"][i]   = {"question": FIXED_QUESTIONS[i], "answer": candidate}
        session["completed"][i] = True
        db.add(DBAnswer(brief_id=sid, question_index=i,
                        question_text=FIXED_QUESTIONS[i], answer_text=candidate))

    await db.execute(update(DBBrief).where(DBBrief.id == sid)
                     .values(completed=session["completed"]))
    await db.commit()

    idx = next_unanswered(session)
    if idx is None:
        return await _do_route(sid, session, db)

    return StartResponse(
        session_id=sid, status="questions",
        question=FIXED_QUESTIONS[idx], question_index=idx,
        total_questions=len(FIXED_QUESTIONS), completed=session["completed"],
    )


# ── /answer ───────────────────────────────────────────────────────────────────
@app.post("/answer", response_model=AnswerResponse)
async def answer(req: AnswerRequest, db: AsyncSession = Depends(get_db)):
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found. Please start a new request.")
    if session["routed"]:
        return AnswerResponse(status="routed", message="Already routed.")

    idx         = next_unanswered(session)
    if idx is None:
        return AnswerResponse(status="routed", message="All questions answered.")

    question    = FIXED_QUESTIONS[idx]
    user_answer = req.answer.strip()

    if not user_answer:
        return AnswerResponse(
            status="vague_retry",
            message=f"Please provide an answer. {EXAMPLE_HINTS.get(idx, '')}",
            question=question, question_index=idx,
        )

    verdict = await check_vague(question, user_answer)
    if verdict.get("vague"):
        hint = EXAMPLE_HINTS.get(idx, "Please be more specific.")
        return AnswerResponse(
            status="vague_retry",
            message=f"That's a bit vague — {verdict.get('reason', 'please clarify')}. {hint}",
            question=question, question_index=idx,
        )

    # Accept this answer
    session["answers"][idx]   = {"question": question, "answer": user_answer}
    session["completed"][idx] = True
    db.add(DBAnswer(brief_id=req.session_id, question_index=idx,
                    question_text=question, answer_text=user_answer))
    await db.execute(update(DBBrief).where(DBBrief.id == req.session_id)
                     .values(completed=session["completed"]))
    await db.commit()

    # ── KEY FIX: check if this answer also contains info for other questions ──
    await _try_fill_from_answer(req.session_id, session, user_answer, db)

    idx2 = next_unanswered(session)
    if idx2 is None:
        resp = await _do_route(req.session_id, session, db)
        return AnswerResponse(
            status="routed", message=resp.message,
            completed=resp.completed, matches=resp.matches,
        )

    return AnswerResponse(
        status="next_question", message="Got it.",
        question=FIXED_QUESTIONS[idx2], question_index=idx2,
        completed=session["completed"],
    )


async def _do_route(sid: str, session: dict, db: AsyncSession) -> StartResponse:
    qa_pairs = [a for a in session["answers"] if a]
    result   = await route_query(session["original_query"], qa_pairs)
    matches  = result["matches"]

    for m in matches:
        db.add(DBMatch(brief_id=sid, person_name=m["name"], person_role=m["role"],
                       confidence=m["confidence"], reason=m["reason"]))

    await db.execute(update(DBBrief).where(DBBrief.id == sid)
                     .values(routed=True, routed_at=datetime.utcnow(),
                             completed=session["completed"]))
    await db.commit()
    session["routed"] = True

    return StartResponse(
        session_id=sid, status="routed",
        message=routing_message(matches),
        total_questions=len(FIXED_QUESTIONS),
        completed=session["completed"], matches=matches,
    )


# ── Admin ─────────────────────────────────────────────────────────────────────
async def _stats(db: AsyncSession) -> dict:
    total    = (await db.scalar(select(func.count(DBBrief.id)))) or 0
    routed   = (await db.scalar(select(func.count(DBBrief.id)).where(DBBrief.routed == True))) or 0
    assigned = select(DBMatch.brief_id.distinct())
    unassigned = (await db.scalar(
        select(func.count(DBBrief.id))
        .where(and_(DBBrief.routed == True, DBBrief.id.not_in(assigned)))
    )) or 0
    per_person = {}
    for p in PEOPLE:
        per_person[p["name"]] = (await db.scalar(
            select(func.count(DBMatch.brief_id.distinct()))
            .where(DBMatch.person_name == p["name"])
        )) or 0
    return {"total": total, "routed": routed,
            "pending": total - routed, "unassigned": unassigned, **per_person}


@app.get("/admin/briefs")
async def admin_briefs(
    person:   Optional[str] = Query(None),
    page:     int           = Query(1, ge=1),
    per_page: int           = Query(50, ge=1, le=200),
    db:       AsyncSession  = Depends(get_db),
):
    stmt = (select(DBBrief)
            .options(selectinload(DBBrief.answers), selectinload(DBBrief.matches))
            .order_by(DBBrief.created_at.desc()))

    if person == "unassigned":
        stmt = stmt.where(and_(DBBrief.routed == True,
                               DBBrief.id.not_in(select(DBMatch.brief_id.distinct()))))
    elif person == "pending":
        stmt = stmt.where(DBBrief.routed == False)
    elif person and person != "all":
        stmt = stmt.where(DBBrief.id.in_(
            select(DBMatch.brief_id.distinct()).where(DBMatch.person_name == person)
        ))

    result     = await db.execute(stmt)
    all_briefs = result.scalars().unique().all()
    page_slice = all_briefs[(page - 1) * per_page: page * per_page]

    return {"total": len(all_briefs), "page": page, "per_page": per_page,
            "stats": await _stats(db), "briefs": [brief_to_dict(b) for b in page_slice]}


@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(SESSIONS)}
