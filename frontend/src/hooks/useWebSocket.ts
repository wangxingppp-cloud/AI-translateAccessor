/**
 * React hook for managing the WebSocket client lifecycle.
 *
 * Connects to the backend, tracks connection state, and exposes
 * send methods for audio (binary) and control (JSON) messages.
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import { WebSocketClient } from '../services/websocket-client';
import type {
  ClientControlMessage,
  ServerMessage,
  ConnectionState,
} from '../types/ws-messages';

interface UseWebSocketOptions {
  /** Backend WebSocket URL. */
  url: string;
  /** Whether to auto-connect on mount. */
  autoConnect?: boolean;
  /** Callback for incoming messages. */
  onMessage?: (message: ServerMessage) => void;
}

interface UseWebSocketReturn {
  /** Current connection state. */
  connectionState: ConnectionState;
  /** Manually connect to the backend. */
  connect: () => void;
  /** Manually disconnect. */
  disconnect: () => void;
  /** Send a binary audio chunk. */
  sendAudioChunk: (chunk: ArrayBuffer) => void;
  /** Send a JSON control message. */
  sendControl: (message: ClientControlMessage) => void;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const { url, autoConnect = true, onMessage } = options;

  const clientRef = useRef<WebSocketClient | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');

  // Initialize client once
  if (!clientRef.current) {
    clientRef.current = new WebSocketClient({ url });
  }

  const client = clientRef.current;

  // Update URL if it changes
  useEffect(() => {
    client.setUrl(url);
  }, [client, url]);

  // Wire up state changes
  useEffect(() => {
    const unsub = client.onStateChange(setConnectionState);
    return unsub;
  }, [client]);

  // Wire up message handler
  useEffect(() => {
    if (!onMessage) return;
    const unsub = client.onMessage(onMessage);
    return unsub;
  }, [client, onMessage]);

  // Auto-connect
  useEffect(() => {
    if (autoConnect) {
      client.connect();
      return () => client.disconnect();
    }
  }, [client, autoConnect]);

  const connect = useCallback(() => client.connect(), [client]);
  const disconnect = useCallback(() => client.disconnect(), [client]);
  const sendAudioChunk = useCallback(
    (chunk: ArrayBuffer) => client.sendAudioChunk(chunk),
    [client],
  );
  const sendControl = useCallback(
    (message: ClientControlMessage) => client.sendControl(message),
    [client],
  );

  return {
    connectionState,
    connect,
    disconnect,
    sendAudioChunk,
    sendControl,
  };
}
