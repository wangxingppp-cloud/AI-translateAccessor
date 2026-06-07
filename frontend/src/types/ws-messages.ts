/**
 * WebSocket message protocol types.
 *
 * Mirrors the backend models in backend/app/models/subtitle.py
 * and backend/app/models/session.py.
 */

// ── Client → Server (Control) ───────────────────────────────────

export interface StartMessage {
  type: 'start';
  session_id?: string;
  config: {
    source_lang?: string;
    target_lang?: string;
    audio_source?: 'microphone' | 'system';
    enable_correction?: boolean;
    glossary?: TermDef[];
    llm?: {
      provider: string;
      apiKey: string;
      model: string;
      baseUrl: string;
      enabled: boolean;
    };
    asr?: {
      provider: string;
      apiKey: string;
      apiSecret: string;
      appId: string;
      baseUrl: string;
    };
  };
}

export interface PauseMessage {
  type: 'pause';
}

export interface ResumeMessage {
  type: 'resume';
}

export interface StopMessage {
  type: 'stop';
}

export interface UpdateGlossaryMessage {
  type: 'update_glossary';
  terms: TermDef[];
}

export interface PingMessage {
  type: 'ping';
}

/** Union of all client → server control messages. */
export type ClientControlMessage =
  | StartMessage
  | PauseMessage
  | ResumeMessage
  | StopMessage
  | UpdateGlossaryMessage
  | PingMessage;

// ── Server → Client ─────────────────────────────────────────────

export interface DiffSegment {
  type: 'unchanged' | 'deleted' | 'inserted';
  text: string;
}

export interface SubtitleDraftMessage {
  type: 'subtitle_draft';
  sequence_id: string;
  original: string;
  translated: string;
  is_sentence_end: boolean;
  is_replace: boolean;       // true = replace current line, false = append
  confidence: number;
  latency_ms: number;
  timestamp: number;
}

export interface SubtitleCorrectedMessage {
  type: 'subtitle_corrected';
  sequence_id: string;
  corrected_text: string;
  diff: DiffSegment[];
  latency_ms: number;
  timestamp: number;
}

export interface SubtitleFinalMessage {
  type: 'subtitle_final';
  sequence_id: string;
  original: string;
  translated: string;
  confidence: number;
  is_corrected: boolean;
  timestamp: number;
}

export interface StatusMessage {
  type: 'status';
  status: 'listening' | 'processing' | 'translating' | 'idle';
  message: string;
  metrics?: {
    audio_buffer_ms: number;
    asr_latency_ms: number;
    translation_latency_ms: number;
    total_latency_ms: number;
  };
}

export interface ErrorMessage {
  type: 'error';
  code: string;
  message: string;
  recoverable: boolean;
  timestamp: number;
}

export interface PongMessage {
  type: 'pong';
  timestamp: number;
}

/** Union of all server → client messages. */
export type ServerMessage =
  | SubtitleDraftMessage
  | SubtitleCorrectedMessage
  | SubtitleFinalMessage
  | StatusMessage
  | ErrorMessage
  | PongMessage;

/** Discriminated union type guard helper. */
export type ServerMessageType = ServerMessage['type'];

// ── Shared ──────────────────────────────────────────────────────

export interface TermDef {
  source: string;
  target: string;
  category?: string;
  priority?: number;
}

// ── Connection State ────────────────────────────────────────────

export type ConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';
