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


# ── History — search ────────────────────────────────────────

@router.get("/subtitles/search")
async def search_subtitles(q: str = Query(..., min_length=1),
                           limit: int = Query(50, ge=1, le=200),
                           svc: HistoryService = Depends(_svc)):
    results = await svc.search_subtitles(q, limit=limit)
    return {
        "query": q,
        "results": [{
            "id": r.id, "session_id": r.session_id,
            "original_text": r.original_text,
            "translated_text": r.translated_text,
            "is_corrected": bool(r.is_corrected),
            "created_at": r.created_at,
        } for r in results]
    }


# ── Glossary ────────────────────────────────────────────────

@router.post("/glossaries")
async def create_glossary(data: dict, svc: HistoryService = Depends(_svc)):
    from ..services.glossary_service import GlossaryService
    gsvc = GlossaryService(svc.db)
    g = await gsvc.create(
        name=data.get("name", "未命名"),
        terms=data.get("terms", []),
        source_lang=data.get("source_lang", "en"),
        target_lang=data.get("target_lang", "zh"),
    )
    return {"id": g.id, "name": g.name, "created_at": g.created_at}


@router.get("/glossaries")
async def list_glossaries(svc: HistoryService = Depends(_svc)):
    from ..services.glossary_service import GlossaryService
    gsvc = GlossaryService(svc.db)
    glossaries = await gsvc.list_all()
    return {"glossaries": [{"id": g.id, "name": g.name, "source_lang": g.source_lang,
            "target_lang": g.target_lang, "created_at": g.created_at} for g in glossaries]}


@router.get("/glossaries/{glossary_id}")
async def get_glossary(glossary_id: str, svc: HistoryService = Depends(_svc)):
    from ..services.glossary_service import GlossaryService
    gsvc = GlossaryService(svc.db)
    data = await gsvc.get(glossary_id)
    if not data:
        return {"error": "not found"}, 404
    g, terms = data["glossary"], data["terms"]
    return {
        "id": g.id, "name": g.name, "source_lang": g.source_lang, "target_lang": g.target_lang,
        "terms": [{"id": t.id, "source": t.source_term, "target": t.target_term,
                    "category": t.category, "priority": t.priority} for t in terms]
    }


@router.delete("/glossaries/{glossary_id}")
async def delete_glossary(glossary_id: str, svc: HistoryService = Depends(_svc)):
    from ..services.glossary_service import GlossaryService
    gsvc = GlossaryService(svc.db)
    await gsvc.delete(glossary_id)
    return {"status": "deleted"}
