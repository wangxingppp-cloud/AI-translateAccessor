"""SQLAlchemy ORM models for translation history."""
import uuid
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


def gen_id():
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=gen_id)
    source_lang = Column(String, default="en")
    target_lang = Column(String, default="zh")
    audio_source = Column(String, default="microphone")
    asr_provider = Column(String, default="local")
    started_at = Column(Float)
    ended_at = Column(Float, nullable=True)
    status = Column(String, default="active")  # active | ended
    total_sentences = Column(Integer, default=0)
    total_duration_ms = Column(Integer, default=0)

    subtitles = relationship("Subtitle", back_populates="session", cascade="all, delete-orphan")


class Subtitle(Base):
    __tablename__ = "subtitles"

    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    sequence_id = Column(String, nullable=False)
    original_text = Column(Text, nullable=False)
    translated_text = Column(Text, default="")
    is_corrected = Column(Integer, default=0)
    asr_confidence = Column(Float, default=0.0)
    created_at = Column(Float)
    position_ms = Column(Integer, default=0)

    session = relationship("Session", back_populates="subtitles")


class Glossary(Base):
    __tablename__ = "glossaries"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    source_lang = Column(String, default="en")
    target_lang = Column(String, default="zh")
    created_at = Column(Float)
    updated_at = Column(Float)

    terms = relationship("GlossaryTerm", back_populates="glossary", cascade="all, delete-orphan")


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"

    id = Column(String, primary_key=True, default=gen_id)
    glossary_id = Column(String, ForeignKey("glossaries.id"), nullable=False)
    source_term = Column(String, nullable=False)
    target_term = Column(String, nullable=False)
    category = Column(String, default="")
    priority = Column(Integer, default=0)
    created_at = Column(Float)

    glossary = relationship("Glossary", back_populates="terms")
