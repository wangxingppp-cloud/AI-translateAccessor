/**
 * WebSocket client for the AI simultaneous interpretation app.
 *
 * Features:
 *   - Binary audio chunk sending (Int16 PCM)
 *   - JSON control message sending
 *   - Auto-reconnect with exponential backoff
 *   - Heartbeat (ping/pong)
 *   - Event-based message dispatching
 */

import type {
  ClientControlMessage,
  ServerMessage,
  ConnectionState,
} from '../types/ws-messages';

export type MessageHandler = (message: ServerMessage) => void;
export type StateChangeHandler = (state: ConnectionState) => void;

export interface WSClientOptions {
  /** Base URL for the backend (e.g. 'ws://127.0.0.1:50840'). */
  url: string;
  /** Max reconnect attempts before giving up. */
  maxReconnectAttempts?: number;
  /** Base reconnect delay in ms (doubles each attempt). */
  reconnectBaseDelay?: number;
  /** Heartbeat interval in ms. */
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
  private _shouldReconnect = true;

  private messageHandlers = new Set<MessageHandler>();
  private stateHandlers = new Set<StateChangeHandler>();

  constructor(options: WSClientOptions) {
    this.url = options.url;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 5;
    this.reconnectBaseDelay = options.reconnectBaseDelay ?? 1000;
    this.heartbeatInterval = options.heartbeatInterval ?? 15000;
  }

  // ── Public API ──────────────────────────────────────────────

  /** Connect to the backend. */
  connect(): void {
    if (this.ws) return;

    this._shouldReconnect = true;
    this._setState('connecting');
    this._connect();
  }

  /** Disconnect and stop reconnection attempts. */
  disconnect(): void {
    this._shouldReconnect = false;
    this._stopHeartbeat();
    this._cancelReconnect();
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this._setState('disconnected');
  }

  /** Send a binary audio chunk (Int16 PCM, 16kHz, mono). */
  sendAudioChunk(chunk: ArrayBuffer): void {
    if (this.state === 'connected' && this.ws) {
      this.ws.send(chunk);
    }
    // If not connected, silently drop (audio is transient)
  }

  /** Send a JSON control message. */
  sendControl(message: ClientControlMessage): void {
    if (this.state === 'connected' && this.ws) {
      this.ws.send(JSON.stringify(message));
    }
  }

  /** Update the backend URL (e.g. after port discovery). */
  setUrl(url: string): void {
    this.url = url;
  }

  /** Register a handler for incoming server messages. */
  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  /** Register a handler for connection state changes. */
  onStateChange(handler: StateChangeHandler): () => void {
    this.stateHandlers.add(handler);
    return () => this.stateHandlers.delete(handler);
  }

  get connectionState(): ConnectionState {
    return this.state;
  }

  // ── Internal ────────────────────────────────────────────────

  private _connect(): void {
    try {
      this.ws = new WebSocket(this.url);
      this.ws.binaryType = 'arraybuffer';

      this.ws.onopen = () => {
        this._setState('connected');
        this.reconnectAttempts = 0;
        this._startHeartbeat();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        if (typeof event.data === 'string') {
          try {
            const message = JSON.parse(event.data) as ServerMessage;
            this._dispatch(message);
          } catch {
            // Ignore unparseable messages
          }
        }
        // Binary responses are not expected from server in this protocol
      };

      this.ws.onclose = (event: CloseEvent) => {
        this._stopHeartbeat();
        this.ws = null;

        if (this._shouldReconnect && event.code !== 1000) {
          this._scheduleReconnect();
        } else {
          this._setState('disconnected');
        }
      };

      this.ws.onerror = () => {
        // onclose will fire after this
      };
    } catch {
      this._scheduleReconnect();
    }
  }

  private _dispatch(message: ServerMessage): void {
    for (const handler of this.messageHandlers) {
      try {
        handler(message);
      } catch {
        // Don't let one handler break others
      }
    }
  }

  private _setState(state: ConnectionState): void {
    this.state = state;
    for (const handler of this.stateHandlers) {
      try {
        handler(state);
      } catch {
        // Ignore handler errors
      }
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
      this.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts),
      30000,
    );

    this._setState('reconnecting');
    this._reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this._connect();
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
