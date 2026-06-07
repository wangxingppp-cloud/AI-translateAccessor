"""SQLite database setup using SQLAlchemy async."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from loguru import logger
from ..config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None

# Increment when schema changes require new columns on existing tables.
_SCHEMA_VERSION = 2


async def _migrate(conn):
    """Apply incremental schema migrations for existing databases."""
    # Check if sessions.name column exists
    result = await conn.execute(text("PRAGMA table_info(sessions)"))
    columns = {row[1] for row in result.fetchall()}
    if "name" not in columns:
        await conn.execute(text("ALTER TABLE sessions ADD COLUMN name VARCHAR DEFAULT ''"))


async def init_db():
    """Initialize database — creates tables if not exist, then migrates."""
    global _engine, _session_factory
    settings = get_settings()
    _engine = create_async_engine(settings.database_url, echo=False)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate(conn)


async def get_session() -> AsyncSession:
    """Get a new async database session."""
    if _session_factory is None:
        await init_db()
    session = _session_factory()
    logger.debug(f"[DB] New AsyncSession created (id={id(session)})")
    return session
