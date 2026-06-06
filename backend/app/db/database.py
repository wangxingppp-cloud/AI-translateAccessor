"""SQLite database setup using SQLAlchemy async."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from ..config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


async def init_db():
    """Initialize database — creates tables if not exist."""
    global _engine, _session_factory
    settings = get_settings()
    _engine = create_async_engine(settings.database_url, echo=False)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Get a new async database session."""
    if _session_factory is None:
        await init_db()
    return _session_factory()
