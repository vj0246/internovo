"""
SQLAlchemy async models — Supabase (PostgreSQL).
Engine is created lazily on first use so the app binds to
the port even if DATABASE_URL isn't set yet (Render env vars
are injected before the first request, after port binding).

Render env var: DATABASE_URL
  Use the Supabase "Transaction pooler" URI (port 6543).
"""
import os
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

# ── Lazy engine (created on first use, not on import) ────────────────────────
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
            raise RuntimeError(
                "DATABASE_URL is not set. "
                "Add it in Render → Environment with your Supabase connection string."
            )
        _engine = create_async_engine(
            _build_url(raw),
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={"statement_cache_size": 0},  # required for Supabase pgbouncer
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
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Models ────────────────────────────────────────────────────────────────────
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
    matches        = relationship("DBMatch",  back_populates="brief",
                                  cascade="all, delete-orphan")


class DBAnswer(Base):
    __tablename__ = "brief_answers"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    brief_id       = Column(String(36), ForeignKey("briefs.id", ondelete="CASCADE"), nullable=False)
    question_index = Column(Integer, nullable=False)
    question_text  = Column(Text, nullable=False)
    answer_text    = Column(Text, nullable=False)
    answered_at    = Column(DateTime, default=datetime.utcnow)
    brief          = relationship("DBBrief", back_populates="answers")


class DBMatch(Base):
    __tablename__ = "brief_matches"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    brief_id    = Column(String(36), ForeignKey("briefs.id", ondelete="CASCADE"), nullable=False)
    person_name = Column(String(100), nullable=False)
    person_role = Column(String(200), nullable=True)
    confidence  = Column(Integer, nullable=False)
    reason      = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    brief       = relationship("DBBrief", back_populates="matches")
