"""
REST API routes — translation history, glossary, health.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_session
from ..services.history_service import HistoryService

router = APIRouter()


def _svc(db: AsyncSession = Depends(get_session)):
    return HistoryService(db)


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


# ── History — sessions ──────────────────────────────────────

@router.get("/sessions")
async def list_sessions(svc: HistoryService = Depends(_svc),
                        limit: int = Query(20, ge=1, le=100),
                        offset: int = Query(0, ge=0)):
    sessions = await svc.list_sessions(limit=limit, offset=offset)
    return {
        "sessions": [{
            "id": s.id,
            "source_lang": s.source_lang,
            "target_lang": s.target_lang,
            "asr_provider": s.asr_provider,
            "started_at": s.started_at,
            "ended_at": s.ended_at,
            "status": s.status,
            "total_sentences": s.total_sentences,
        } for s in sessions]
    }


@router.get("/sessions/{session_id}/subtitles")
async def get_session_subtitles(session_id: str,
                                svc: HistoryService = Depends(_svc)):
    subs = await svc.get_session_subtitles(session_id)
    if subs is None:
        return {"error": "not found"}, 404
    return {
        "session_id": session_id,
        "subtitles": [{
            "id": s.id, "sequence_id": s.sequence_id,
            "original_text": s.original_text,
            "translated_text": s.translated_text,
            "is_corrected": bool(s.is_corrected),
            "created_at": s.created_at,
        } for s in subs]
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str,
                         svc: HistoryService = Depends(_svc)):
    await svc.delete_session(session_id)
    return {"status": "deleted"}


# ── Glossary (stub) ─────────────────────────────────────────

@router.get("/glossaries")
async def list_glossaries():
    return {"glossaries": []}
