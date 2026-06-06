/**
 * Connection state store — tracks WebSocket + backend status.
 */
import { create } from 'zustand';
import type { ConnectionState } from '../types/ws-messages';

interface ConnectionStore {
  /** WebSocket connection state. */
  wsState: ConnectionState;
  setWsState: (state: ConnectionState) => void;

  /** Discovered backend port (null before backend starts). */
  backendPort: number | null;
  setBackendPort: (port: number | null) => void;

  /** Backend error message (null if healthy). */
  backendError: string | null;
  setBackendError: (msg: string | null) => void;
}

export const useConnectionStore = create<ConnectionStore>((set) => ({
  wsState: 'disconnected',
  setWsState: (wsState) => set({ wsState }),

  backendPort: null,
  setBackendPort: (backendPort) => set({ backendPort }),

  backendError: null,
  setBackendError: (backendError) => set({ backendError }),
}));
