/**
 * React hook for audio capture lifecycle.
 *
 * Manages the AudioCaptureService instance within a React component,
 * exposing audio source selection, state, and chunk callback binding.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { audioCapture, type AudioChunkHandler } from '../services/audio-capture';
import type {
  AudioSource,
  AudioCaptureConfig,
  AudioCaptureState,
  AudioCaptureError,
} from '../types/audio';
import { AUDIO_FORMAT } from '../types/audio';
import type { SystemAudioDeviceInfo } from '../types/electron';

interface UseAudioCaptureOptions {
  /** Callback for each PCM audio chunk (16kHz, 16bit, mono). */
  onChunk?: AudioChunkHandler;
  /** Initial audio source. */
  defaultSource?: AudioSource;
  /** Auto-start capture on mount. */
  autoStart?: boolean;
}

interface UseAudioCaptureReturn {
  /** Current capture state. */
  state: AudioCaptureState;
  /** Currently selected audio source. */
  source: AudioSource;
  /** Known audio format. */
  format: typeof AUDIO_FORMAT;
  /** System audio devices (for source selection). */
  systemDevices: SystemAudioDeviceInfo[];
  /** Start capturing from the given source. */
  startCapture: (source: AudioSource, deviceId?: string) => Promise<void>;
  /** Stop capture. */
  stopCapture: () => Promise<void>;
  /** Switch audio source. */
  switchSource: (source: AudioSource, deviceId?: string) => Promise<void>;
  /** Latest error, if any. */
  error: AudioCaptureError | null;
  /** Clear the error. */
  clearError: () => void;
}

export function useAudioCapture(options: UseAudioCaptureOptions = {}): UseAudioCaptureReturn {
  const { onChunk, defaultSource = 'microphone', autoStart = false } = options;

  const [state, setState] = useState<AudioCaptureState>('idle');
  const [source, setSource] = useState<AudioSource>(defaultSource);
  const [error, setError] = useState<AudioCaptureError | null>(null);
  const [systemDevices, setSystemDevices] = useState<SystemAudioDeviceInfo[]>([]);

  const onChunkRef = useRef(onChunk);
  onChunkRef.current = onChunk;

  // Wire up callbacks on mount
  useEffect(() => {
    audioCapture.onChunk((chunk) => onChunkRef.current?.(chunk));
    audioCapture.onStateChange(setState);
    audioCapture.onError((err) => {
      setError(err);
      setState('error');
    });

    // Load system devices list
    audioCapture.listSystemDevices().then(setSystemDevices);

    return () => {
      audioCapture.stop();
    };
  }, []);

  // Auto-start
  useEffect(() => {
    if (autoStart) {
      audioCapture.start(defaultSource);
      setSource(defaultSource);
      return () => { audioCapture.stop(); };
    }
  }, [autoStart, defaultSource]);

  const startCapture = useCallback(async (src: AudioSource, deviceId?: string) => {
    setError(null);
    setSource(src);
    await audioCapture.start(src, deviceId);
  }, []);

  const stopCapture = useCallback(async () => {
    await audioCapture.stop();
  }, []);

  const switchSource = useCallback(async (src: AudioSource, deviceId?: string) => {
    setError(null);
    setSource(src);
    await audioCapture.switchSource(src, deviceId);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return {
    state,
    source,
    format: AUDIO_FORMAT,
    systemDevices,
    startCapture,
    stopCapture,
    switchSource,
    error,
    clearError,
  };
}
