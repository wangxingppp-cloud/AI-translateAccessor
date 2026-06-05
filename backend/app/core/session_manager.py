"""
Session manager — tracks state and configuration for each WebSocket session.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from ..models.glossary import Term


class SessionState(str, Enum):
    """Translation session state machine."""
    IDLE = "idle"              # Connected but not translating
    LISTENING = "listening"    # Receiving audio, pipeline active
    PAUSED = "paused"          # Temporarily paused by user
    ERROR = "error"            # Error state, waiting for recovery
    ENDED = "ended"            # Session ended


@dataclass
class SessionConfig:
    """Configuration for a translation session."""
    source_lang: str = "en"
    target_lang: str = "zh"
    audio_source: str = "microphone"     # "microphone" | "system"
    enable_correction: bool = True
    glossary_terms: list[Term] = field(default_factory=list)


@dataclass
class Session:
    """Runtime state for one client's translation session."""
    session_id: str
    config: SessionConfig = field(default_factory=SessionConfig)
    state: SessionState = SessionState.IDLE
    total_audio_chunks: int = 0
    total_sentences: int = 0
    last_activity: float = 0.0


class SessionManager:
    """Manages session lifecycle — create, update, query, destroy."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._max_sessions: int = 50

    def create(self, session_id: str, config: Optional[SessionConfig] = None) -> Session:
        """Create a new session. Raises RuntimeError if at capacity."""
        if len(self._sessions) >= self._max_sessions:
            raise RuntimeError(
                f"Max concurrent sessions ({self._max_sessions}) reached"
            )
        session = Session(
            session_id=session_id,
            config=config or SessionConfig(),
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        """Get a session or None."""
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> Session:
        """Get a session or raise KeyError."""
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id} not found")
        return self._sessions[session_id]

    def update_state(self, session_id: str, state: SessionState) -> None:
        """Transition a session to a new state."""
        session = self.require(session_id)
        session.state = state

    def remove(self, session_id: str) -> None:
        """Remove a session."""
        self._sessions.pop(session_id, None)

    def record_audio_chunk(self, session_id: str) -> None:
        """Increment audio chunk counter."""
        session = self._sessions.get(session_id)
        if session:
            session.total_audio_chunks += 1

    def record_sentence(self, session_id: str) -> None:
        """Increment translated sentence counter."""
        session = self._sessions.get(session_id)
        if session:
            session.total_sentences += 1

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    @property
    def is_at_capacity(self) -> bool:
        return len(self._sessions) >= self._max_sessions


# Singleton
sessions = SessionManager()
