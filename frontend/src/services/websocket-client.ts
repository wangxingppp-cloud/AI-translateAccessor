/**
 * WebSocket client for the AI simultaneous interpretation app.
 *
 * Features:
 *   - Binary audio chunk sending (Int16 PCM)
 *   - JSON control message sending
 *   - Auto-reconnect with exponential backoff (on unexpected disconnect)
 *   - Heartbeat (ping/pong)
 *   - Event-based message dispatching
 */
import type {
  ClientControlMessage, ServerMessage, ConnectionState,
} from '../types/ws-messages';

export type MessageHandler = (message: ServerMessage) => void;
export type StateChangeHandler = (state: ConnectionState) => void;

export interface WSClientOptions {
  url: string;
  maxReconnectAttempts?: number;
  reconnectBaseDelay?: number;
  heartbeatInterval?: number;
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private state: ConnectionState = 'disconnected';
  private reconnectAttempts = 0;
  private maxReconnectAttempts: number;
  private reconnectBaseDelay: number;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private heartbeatInterval: number;
  private _shouldReconnect = false;
  private _intentionalClose = false;

  private messageHandlers = new Set<MessageHandler>();
  private stateHandlers = new Set<StateChangeHandler>();

  constructor(options: WSClientOptions) {
    this.url = options.url;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 5;
    this.reconnectBaseDelay = options.reconnectBaseDelay ?? 1000;
    this.heartbeatInterval = options.heartbeatInterval ?? 15000;
  }

  // ── Public API ──────────────────────────────────────────────

  /** Connect to the backend. Always opens a fresh socket. */
  connect(): void {
    this._shouldReconnect = true;
    this._intentionalClose = false;
    this._setState('connecting');
    this._open();
  }

  /** Disconnect and stop reconnection. */
  disconnect(): void {
    this._shouldReconnect = false;
    this._intentionalClose = true;
    this._stopHeartbeat();
    this._cancelReconnect();
    this._closeSocket();
    this._setState('disconnected');
  }

  /** Send a binary audio chunk (Int16 PCM, 16kHz, mono). */
  sendAudioChunk(chunk: ArrayBuffer): void {
    if (this.state === 'connected' && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(chunk);
    }
  }

  /** Send a JSON control message. */
  sendControl(message: ClientControlMessage): void {
    if (this.state === 'connected' && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  setUrl(url: string): void { this.url = url; }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  onStateChange(handler: StateChangeHandler): () => void {
    this.stateHandlers.add(handler);
    return () => this.stateHandlers.delete(handler);
  }

  get connectionState(): ConnectionState { return this.state; }

  // ── Internal ────────────────────────────────────────────────

  private _open(): void {
    // Force-close any existing socket (prevents ghost onclose interference)
    this._closeSocket();

    let socket: WebSocket;
    try {
      socket = new WebSocket(this.url);
      socket.binaryType = 'arraybuffer';
    } catch {
      this._setState('disconnected');
      return;
    }
    this.ws = socket;

    socket.onopen = () => {
      this._setState('connected');
      this.reconnectAttempts = 0;
      this._startHeartbeat();
    };

    socket.onmessage = (event: MessageEvent) => {
      if (typeof event.data === 'string') {
        try {
          this._dispatch(JSON.parse(event.data) as ServerMessage);
        } catch { /* ignore */ }
      }
    };

    socket.onclose = (event: CloseEvent) => {
      this._stopHeartbeat();

      if (!this._shouldReconnect || event.code === 1000) {
        this._setState('disconnected');
        return;
      }
      this._scheduleReconnect();
    };

    socket.onerror = () => { /* onclose follows */ };
  }

  private _closeSocket(): void {
    if (this.ws) {
      const s = this.ws;
      this.ws = null;
      s.onopen = null;
      s.onmessage = null;
      s.onclose = null;
      s.onerror = null;
      try { s.close(); } catch { /* already closed */ }
    }
  }

  private _dispatch(message: ServerMessage): void {
    for (const handler of this.messageHandlers) {
      try { handler(message); } catch { /* ignore */ }
    }
  }

  private _setState(state: ConnectionState): void {
    this.state = state;
    for (const handler of this.stateHandlers) {
      try { handler(state); } catch { /* ignore */ }
    }
  }

  // ── Reconnection ─────────────────────────────────────────────

  private _reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this._setState('disconnected');
      return;
    }
    const delay = Math.min(
      this.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts), 30000,
    );
    this._setState('reconnecting');
    this._reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this._open();
    }, delay);
  }

  private _cancelReconnect(): void {
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
  }

  // ── Heartbeat ────────────────────────────────────────────────

  private _startHeartbeat(): void {
    this._stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.sendControl({ type: 'ping' });
    }, this.heartbeatInterval);
  }

  private _stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
}
