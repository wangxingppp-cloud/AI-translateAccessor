"""
REST API routes for non-streaming operations:
- Translation history (CRUD, search, export)
- Glossary management (CRUD)
- Session management
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


# ── Translation history (stubs — implemented in history module) ──
@router.get("/sessions")
async def list_sessions():
    return {"sessions": []}


@router.get("/sessions/{session_id}/subtitles")
async def get_session_subtitles(session_id: str):
    return {"session_id": session_id, "subtitles": []}


# ── Glossary management (stubs — implemented in glossary module) ──
@router.get("/glossaries")
async def list_glossaries():
    return {"glossaries": []}
