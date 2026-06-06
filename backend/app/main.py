"""
AI Simultaneous Interpretation Backend
FastAPI application entry point.

Desktop packaging mode:
  The backend is spawned as a child process by Electron.  It listens on
  an OS-assigned port (port=0) and prints the bound port to stdout as:
      AI_TRANSLATE_READY port=XXXXX
  The Electron main process reads this line to discover the backend URL.

Dev mode:
  Set PORT=8000 (or any fixed port) in .env for a predictable dev URL.
"""
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api.ws import router as ws_router
from .api.rest import router as rest_router
from .utils.logger import setup_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    settings = get_settings()
    setup_logger(settings.log_level)
    from .db.database import init_db
    await init_db()
    yield


def create_app() -> FastAPI:
    """Factory to create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="AI Simultaneous Interpretation",
        description="Real-time speech recognition, translation, and subtitling API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(ws_router)
    app.include_router(rest_router, prefix="/api")

    return app


app = create_app()


# ── Standalone entry point for PyInstaller / desktop packaging ──────
# When bundled, the entry point is this function, not `uvicorn` CLI.
def main():
    """Run the backend server and print the bound port to stdout.

    Port discovery strategy:
      1. If settings.port == 0, bind a temporary socket to get an OS-assigned port.
      2. Pass that resolved port to uvicorn.
      3. Print ``AI_TRANSLATE_READY port=XXXXX`` to stdout.
      4. Write the port to ``<data_dir>/.backend_port`` as a backup.

    Electron reads stdout line-by-line to discover the backend URL:
      ws://127.0.0.1:<port>/ws/translate

    Called from:
      - ``python -m app.main``              (dev)
      - ``ai-translate-backend.exe``        (PyInstaller bundled)
    """
    import socket
    import uvicorn
    from loguru import logger

    settings = get_settings()

    # Resolve port: 0 → OS auto-assign via a temporary socket
    if settings.port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((settings.host, 0))
            actual_port = s.getsockname()[1]
    else:
        actual_port = settings.port

    # Write port to stdout (structured line for Electron)
    sys.stdout.write(f"AI_TRANSLATE_READY port={actual_port}\n")
    sys.stdout.flush()

    # Backup: write port to a ready-file
    ready_file = settings.resolved_data_dir / ".backend_port"
    ready_file.parent.mkdir(parents=True, exist_ok=True)
    ready_file.write_text(str(actual_port))

    logger.info(f"Backend starting on http://{settings.host}:{actual_port}")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=actual_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
