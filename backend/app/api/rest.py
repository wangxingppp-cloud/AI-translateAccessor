"""
REST API routes — translation history, glossary, health, TTS.
"""
import asyncio
import wave
import io

import numpy as np
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_session
from ..services.history_service import HistoryService

router = APIRouter()


def _svc(db: AsyncSession = Depends(get_session)):
    return HistoryService(db)


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


# ── TTS ────────────────────────────────────────────────────

@router.post("/tts")
async def tts_synthesize(data: dict):
    """Synthesize speech from text using sherpa-onnx ZipVoice TTS.

    Request body: {"text": "要合成的文字"}
    Response: WAV audio bytes (audio/wav)
    """
    text = (data.get("text") or "").strip()
    if not text:
        return Response(content='{"error":"text is empty"}', status_code=400, media_type="application/json")
    if len(text) > 500:
        text = text[:500]

    try:
        from ..engines.tts.tts_engine import get_tts_engine
        engine = get_tts_engine()
        if not engine.is_ready():
            return Response(content='{"error":"TTS model not loaded"}', status_code=503, media_type="application/json")

        samples, sample_rate = await engine.synthesize_async(text)

        if len(samples) == 0:
            return Response(content='{"error":"TTS returned empty audio"}', status_code=500, media_type="application/json")

        # float32 → int16 PCM → WAV
        pcm_int16 = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_int16.tobytes())

        return Response(content=buf.getvalue(), media_type="audio/wav")

    except Exception as e:
        logger.error(f"[TTS-API] ERROR: {e}", exc_info=True)
        return Response(content=f'{{"error":"{e}"}}', status_code=500, media_type="application/json")


@router.get("/debug/db-check")
async def debug_db_check():
    """Debug endpoint: directly query SQLite to verify data."""
    from ..db.database import get_session as get_db_session
    from ..db.models import Session, Subtitle
    from sqlalchemy import select, func, text as sql_text

    db = await get_db_session()
    try:
        # Count sessions
        result = await db.execute(select(func.count()).select_from(Session))
        session_count = result.scalar()

        # Count subtitles
        result = await db.execute(select(func.count()).select_from(Subtitle))
        subtitle_count = result.scalar()

        # List all sessions
        result = await db.execute(select(Session).order_by(Session.started_at.desc()).limit(10))
        sessions = []
        for s in result.scalars().all():
            sessions.append({
                "id": s.id, "name": s.name, "status": s.status,
                "total_sentences": s.total_sentences, "started_at": s.started_at,
            })

        # Get DB file path
        from ..config import get_settings
        db_url = get_settings().database_url

        return {
            "database_url": db_url,
            "session_count": session_count,
            "subtitle_count": subtitle_count,
            "recent_sessions": sessions,
        }
    finally:
        await db.close()


# ── History — sessions ──────────────────────────────────────

@router.get("/sessions")
async def list_sessions(svc: HistoryService = Depends(_svc),
                        limit: int = Query(20, ge=1, le=100),
                        offset: int = Query(0, ge=0)):
    logger.info(f"[REST] GET /sessions limit={limit} offset={offset}")
    sessions = await svc.list_sessions(limit=limit, offset=offset)
    logger.info(f"[REST] Found {len(sessions)} sessions")
    result = []
    for s in sessions:
        logger.debug(f"[REST]   session id={s.id} name={s.name!r} status={s.status} sentences={s.total_sentences}")
        result.append({
            "id": s.id,
            "name": s.name or "",
            "source_lang": s.source_lang,
            "target_lang": s.target_lang,
            "asr_provider": s.asr_provider,
            "started_at": s.started_at,
            "ended_at": s.ended_at,
            "status": s.status,
            "total_sentences": s.total_sentences,
        })
    return {"sessions": result}


@router.post("/sessions")
async def create_session(data: dict, svc: HistoryService = Depends(_svc)):
    """Save a completed translation session with subtitles."""
    subtitle_count = len(data.get("subtitles", []))
    logger.info(f"[REST] POST /sessions name={data.get('name')!r} subtitles={subtitle_count} "
                f"src={data.get('source_lang')} tgt={data.get('target_lang')}")
    try:
        s = await svc.create_session_with_subtitles(
            name=data.get("name", "未命名"),
            source_lang=data.get("source_lang", "en"),
            target_lang=data.get("target_lang", "zh"),
            subtitles=data.get("subtitles", []),
        )
        logger.info(f"[REST] POST /sessions → saved id={s.id} sentences={s.total_sentences}")
        return {"id": s.id, "status": "saved", "total_sentences": s.total_sentences}
    except Exception as e:
        logger.error(f"[REST] POST /sessions FAILED: {e}", exc_info=True)
        raise


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
