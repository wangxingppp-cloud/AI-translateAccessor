/**
 * TTS playback store — global audio playback manager.
 *
 * Single AudioContext shared across all subtitle lines.
 * Only one line can play at a time; clicking another line
 * stops the current playback first.
 */
import { create } from 'zustand';
import { fetchTTS } from '../services/tts-client';

// Module-level AudioContext (shared, lazy-init)
let audioCtx: AudioContext | null = null;
let currentSource: AudioBufferSourceNode | null = null;

function getAudioCtx(): AudioContext {
  if (!audioCtx || audioCtx.state === 'closed') {
    audioCtx = new AudioContext();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

function stopCurrent() {
  if (currentSource) {
    try { currentSource.stop(); } catch { /* already stopped */ }
    currentSource = null;
  }
}

interface TTSStore {
  playingId: string | null;
  loadingId: string | null;
  play: (id: string, text: string, backendPort: number) => Promise<void>;
  stop: () => void;
}

export const useTTSStore = create<TTSStore>((set, get) => ({
  playingId: null,
  loadingId: null,

  play: async (id, text, backendPort) => {
    const { playingId } = get();

    // If clicking the same line that's playing, stop it
    if (playingId === id) {
      stopCurrent();
      set({ playingId: null, loadingId: null });
      return;
    }

    // Stop any current playback
    stopCurrent();
    set({ loadingId: id, playingId: null });

    try {
      const wavBuf = await fetchTTS(text, backendPort);
      const ctx = getAudioCtx();
      const audioBuf = await ctx.decodeAudioData(wavBuf.slice(0));

      // Check if still the active request (user may have clicked another line)
      if (get().loadingId !== id) return;

      const source = ctx.createBufferSource();
      source.buffer = audioBuf;
      source.connect(ctx.destination);
      currentSource = source;

      source.onended = () => {
        if (currentSource === source) currentSource = null;
        set((s) => s.playingId === id ? { playingId: null, loadingId: null } : {});
      };

      source.start(0);
      set({ playingId: id, loadingId: null });
    } catch (err) {
      console.error('[TTS] playback error:', err);
      if (get().loadingId === id) {
        set({ playingId: null, loadingId: null });
      }
    }
  },

  stop: () => {
    stopCurrent();
    set({ playingId: null, loadingId: null });
  },
}));
