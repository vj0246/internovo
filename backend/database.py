"""
Supabase (PostgreSQL) via Session pooler.

DATABASE_URL must use the Session pooler (port 5432 on pooler host):
  postgresql://postgres.[ref]:[PASSWORD]@aws-0-[region].pooler.supabase.com:5432/postgres

NOT transaction pooler (6543) — that breaks prepared statements.
NOT direct (db. host) — unreachable from Render free tier.
"""
import os
import logging
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.pool import NullPool

log = logging.getLogger(__name__)

_engine          = None
_session_factory = None


def _build_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgresql://") and "+asyncpg" not in raw:
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


def get_engine():
    global _engine
    if _engine is None:
        raw = os.environ.get("DATABASE_URL", "")
        if not raw:
            raise RuntimeError("DATABASE_URL is not set.")
        _engine = create_async_engine(
            _build_url(raw),
            poolclass=NullPool,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
            },
            echo=False,
        )
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def get_db():
    async with _get_session_factory()() as session:
        yield session


async def init_db():
    """Create tables. If it fails (pooler quirk, tables exist), log and continue."""
    try:
        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("Database tables ready.")
    except Exception as exc:
        log.warning(
            "init_db failed (%s). If tables already exist in Supabase, this is fine. "
            "Otherwise, run the CREATE TABLE SQL manually in the Supabase SQL editor.",
            exc,
        )


class Base(DeclarativeBase):
    pass


class DBBrief(Base):
    __tablename__ = "briefs"
    id             = Column(String(36), primary_key=True)
    original_query = Column(Text, nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed      = Column(JSON, default=lambda: [False] * 5, nullable=False)
    routed         = Column(Boolean, default=False, nullable=False)
    routed_at      = Column(DateTime, nullable=True)
    answers        = relationship("DBAnswer", back_populates="brief",
                                  cascade="all, delete-orphan",
                                  order_by="DBAnswer.question_index")
    matches        = relationship("DBMatch", back_populates="brief",
                                  cascade="all, delete-orphan")


class DBAnswer(Base):
    __tablename__ = "brief_answers"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    brief_id       = Column(String(36), ForeignKey("briefs.id", ondelete="CASCADE"))
    question_index = Column(Integer, nullable=False)
    question_text  = Column(Text, nullable=False)
    answer_text    = Column(Text, nullable=False)
    answered_at    = Column(DateTime, default=datetime.utcnow)
    brief          = relationship("DBBrief", back_populates="answers")


class DBMatch(Base):
    __tablename__ = "brief_matches"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    brief_id    = Column(String(36), ForeignKey("briefs.id", ondelete="CASCADE"))
    person_name = Column(String(100), nullable=False)
    person_role = Column(String(200), nullable=True)
    confidence  = Column(Integer, nullable=False)
    reason      = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    brief       = relationship("DBBrief", back_populates="matches")


# ── Manual SQL (run in Supabase SQL Editor if auto-create fails) ──────────
MANUAL_SQL = """
CREATE TABLE IF NOT EXISTS briefs (
    id             VARCHAR(36) PRIMARY KEY,
    original_query TEXT NOT NULL,
    created_at     TIMESTAMP DEFAULT NOW() NOT NULL,
    completed      JSONB DEFAULT '[false,false,false,false,false]' NOT NULL,
    routed         BOOLEAN DEFAULT FALSE NOT NULL,
    routed_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS brief_answers (
    id             SERIAL PRIMARY KEY,
    brief_id       VARCHAR(36) REFERENCES briefs(id) ON DELETE CASCADE,
    question_index INTEGER NOT NULL,
    question_text  TEXT NOT NULL,
    answer_text    TEXT NOT NULL,
    answered_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS brief_matches (
    id          SERIAL PRIMARY KEY,
    brief_id    VARCHAR(36) REFERENCES briefs(id) ON DELETE CASCADE,
    person_name VARCHAR(100) NOT NULL,
    person_role VARCHAR(200),
    confidence  INTEGER NOT NULL,
    reason      TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);
"""