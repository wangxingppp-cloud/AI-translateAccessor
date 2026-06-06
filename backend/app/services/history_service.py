"""Translation history service — CRUD for sessions and subtitles."""
import time
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import Session, Subtitle


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
        sub = Subtitle(id=str(uuid.uuid4()), session_id=session_id,
                       sequence_id=sequence_id, original_text=original,
                       translated_text=translated, is_corrected=int(is_corrected),
                       asr_confidence=confidence, created_at=time.time(),
                       position_ms=position_ms)
        self.db.add(sub)
        await self.db.commit()

    async def list_sessions(self, limit=20, offset=0):
        q = select(Session).order_by(desc(Session.started_at)).limit(limit).offset(offset)
        result = await self.db.execute(q)
        return result.scalars().all()

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


import uuid as _uuid

def uuid():
    return str(_uuid.uuid4())
