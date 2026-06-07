"""Translation history service — CRUD for sessions and subtitles."""
import time
import uuid as _uuid_mod
from loguru import logger
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import Session, Subtitle


def _gen_id():
    return str(_uuid_mod.uuid4())


class HistoryService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, session_id: str, source_lang="en", target_lang="zh",
                             audio_source="microphone", asr_provider="local") -> Session:
        s = Session(id=session_id, source_lang=source_lang, target_lang=target_lang,
                    audio_source=audio_source, asr_provider=asr_provider,
                    started_at=time.time(), status="active")
        self.db.add(s)
        await self.db.commit()
        return s

    async def create_session_with_subtitles(
        self, name: str, source_lang="en", target_lang="zh",
        subtitles: list[dict] | None = None,
    ) -> Session:
        """Create a session and bulk-insert subtitles in one transaction."""
        session_id = _gen_id()
        now = time.time()
        sub_count = len(subtitles) if subtitles else 0
        logger.info(f"[DB] create_session_with_subtitles: id={session_id} name={name!r} "
                    f"subtitles={sub_count} src={source_lang} tgt={target_lang}")

        s = Session(
            id=session_id, name=name, source_lang=source_lang, target_lang=target_lang,
            started_at=now, ended_at=now, status="ended",
            total_sentences=sub_count,
        )
        self.db.add(s)
        logger.debug(f"[DB] Session object added, flushing...")
        await self.db.flush()  # get session_id available for FK
        logger.debug(f"[DB] Flush OK, session_id={session_id}")

        if subtitles:
            for idx, sub in enumerate(subtitles):
                self.db.add(Subtitle(
                    id=_gen_id(), session_id=session_id,
                    sequence_id=str(idx),
                    original_text=sub.get("original", ""),
                    translated_text=sub.get("translated", ""),
                    created_at=sub.get("timestamp", now),
                ))
            logger.debug(f"[DB] Added {sub_count} Subtitle objects")

        logger.debug(f"[DB] Committing transaction...")
        await self.db.commit()
        logger.info(f"[DB] COMMIT OK — session {session_id} saved with {sub_count} subtitles")

        # Verify: re-read from DB to confirm persistence
        verify = await self.db.get(Session, session_id)
        if verify:
            logger.info(f"[DB] VERIFY OK — session {session_id} exists in DB, name={verify.name!r}")
        else:
            logger.error(f"[DB] VERIFY FAILED — session {session_id} NOT found after commit!")

        return s

    async def list_sessions(self, limit=20, offset=0):
        logger.debug(f"[DB] list_sessions limit={limit} offset={offset}")
        q = select(Session).order_by(desc(Session.started_at)).limit(limit).offset(offset)
        result = await self.db.execute(q)
        rows = result.scalars().all()
        logger.info(f"[DB] list_sessions returned {len(rows)} rows")
        for r in rows:
            logger.debug(f"[DB]   → id={r.id} name={r.name!r} status={r.status} sentences={r.total_sentences}")
        return rows

    async def end_session(self, session_id: str, total_sentences=0, total_duration_ms=0):
        s = await self.db.get(Session, session_id)
        if s:
            s.ended_at = time.time()
            s.status = "ended"
            s.total_sentences = total_sentences
            s.total_duration_ms = total_duration_ms
            await self.db.commit()

    async def add_subtitle(self, session_id: str, sequence_id: str, original: str,
                           translated: str, is_corrected=False, confidence=0.0,
                           position_ms=0):
        sub = Subtitle(id=_gen_id(), session_id=session_id,
                       sequence_id=sequence_id, original_text=original,
                       translated_text=translated, is_corrected=int(is_corrected),
                       asr_confidence=confidence, created_at=time.time(),
                       position_ms=position_ms)
        self.db.add(sub)
        await self.db.commit()

    async def get_session_subtitles(self, session_id: str):
        s = await self.db.get(Session, session_id)
        if not s:
            return None
        q = select(Subtitle).where(Subtitle.session_id == session_id).order_by(Subtitle.created_at)
        result = await self.db.execute(q)
        return result.scalars().all()

    async def search_subtitles(self, query: str, limit=50):
        q = (select(Subtitle)
             .where(Subtitle.original_text.contains(query) | Subtitle.translated_text.contains(query))
             .order_by(desc(Subtitle.created_at)).limit(limit))
        result = await self.db.execute(q)
        return result.scalars().all()

    async def delete_session(self, session_id: str):
        s = await self.db.get(Session, session_id)
        if s:
            await self.db.delete(s)
            await self.db.commit()
