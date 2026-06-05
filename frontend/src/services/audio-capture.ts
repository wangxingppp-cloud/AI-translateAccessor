/**
 * Audio capture service — unified interface for microphone and system audio.
 *
 * Microphone capture:
 *   Uses Web Audio API (navigator.mediaDevices.getUserMedia) in the renderer.
 *   Works cross-platform without IPC. Outputs PCM chunks to a callback.
 *
 * System audio capture:
 *   Invokes OS-specific native capture in the Electron main process via IPC.
 *   The main process spawns a platform-specific helper and forwards PCM chunks.
 */
import type {
  AudioSource,
  AudioCaptureConfig,
  AudioCaptureState,
  AudioCaptureError,
  AUDIO_FORMAT,
} from '../types/audio';
import type { SystemAudioDeviceInfo } from '../types/electron';

export type AudioChunkHandler = (chunk: ArrayBuffer) => void;
export type AudioStateHandler = (state: AudioCaptureState) => void;
export type AudioErrorHandler = (error: AudioCaptureError) => void;

// The actual 16kHz sample rate we resample to
const TARGET_SAMPLE_RATE = 16000;

export class AudioCaptureService {
  // ── State ─────────────────────────────────────────────────
  private _source: AudioSource = 'microphone';
  private _state: AudioCaptureState = 'idle';
  private _audioContext: AudioContext | null = null;
  private _mediaStream: MediaStream | null = null;
  private _scriptProcessor: ScriptProcessorNode | null = null;
  private _systemUnsubscribers: (() => void)[] = [];

  // ── Callbacks ─────────────────────────────────────────────
  private _onChunk: AudioChunkHandler | null = null;
  private _onStateChange: AudioStateHandler | null = null;
  private _onError: AudioErrorHandler | null = null;

  // ── Public API ────────────────────────────────────────────

  /** Select audio source and begin capture. */
  async start(
    source: AudioSource,
    deviceId?: string,
  ): Promise<void> {
    this._source = source;

    if (source === 'microphone') {
      await this._startMicrophone(deviceId);
    } else {
      await this._startSystemAudio(deviceId);
    }
  }

  /** Stop active capture and release resources. */
  async stop(): Promise<void> {
    if (this._source === 'microphone') {
      this._stopMicrophone();
    } else {
      await this._stopSystemAudio();
    }
    this._setState('idle');
  }

  /** Switch audio source on-the-fly. */
  async switchSource(source: AudioSource, deviceId?: string): Promise<void> {
    await this.stop();
    await this.start(source, deviceId);
  }

  /** List available system audio devices. */
  async listSystemDevices(): Promise<SystemAudioDeviceInfo[]> {
    const api = window.electronAPI;
    if (!api) return [];
    try {
      return await api.audio.listDevices();
    } catch {
      return [];
    }
  }

  /** Get the current audio source. */
  get source(): AudioSource { return this._source; }

  /** Get current capture state. */
  get state(): AudioCaptureState { return this._state; }

  // ── Callback registration ─────────────────────────────────

  onChunk(handler: AudioChunkHandler): void { this._onChunk = handler; }
  onStateChange(handler: AudioStateHandler): void { this._onStateChange = handler; }
  onError(handler: AudioErrorHandler): void { this._onError = handler; }

  // ── Microphone (renderer, cross-platform) ──────────────────

  private async _startMicrophone(deviceId?: string): Promise<void> {
    this._setState('requesting');

    try {
      this._mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: { ideal: TARGET_SAMPLE_RATE },
          channelCount: { ideal: 1 },
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
        },
      });

      this._audioContext = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });

      const source = this._audioContext.createMediaStreamSource(this._mediaStream);
      this._scriptProcessor = this._audioContext.createScriptProcessor(4096, 1, 1);

      this._scriptProcessor.onaudioprocess = (event) => {
        if (this._state !== 'capturing') return;
        const input = event.inputBuffer.getChannelData(0);
        // Convert Float32 [-1, +1] → Int16 PCM
        const pcm = float32ToInt16(input);
        this._onChunk?.(pcm.buffer.slice(pcm.byteOffset, pcm.byteOffset + pcm.byteLength));
      };

      source.connect(this._scriptProcessor);
      this._scriptProcessor.connect(this._audioContext.destination);

      this._setState('capturing');
    } catch (err) {
      this._setState('error');
      this._onError?.({
        code: 'MIC_PERMISSION',
        message: `Microphone access denied: ${(err as Error).message}`,
        recoverable: true,
      });
    }
  }

  private _stopMicrophone(): void {
    if (this._scriptProcessor) {
      this._scriptProcessor.disconnect();
      this._scriptProcessor = null;
    }
    if (this._audioContext) {
      this._audioContext.close();
      this._audioContext = null;
    }
    if (this._mediaStream) {
      this._mediaStream.getTracks().forEach((t) => t.stop());
      this._mediaStream = null;
    }
  }

  // ── System audio (main process, OS-specific) ───────────────

  private async _startSystemAudio(deviceId?: string): Promise<void> {
    const api = window.electronAPI;
    if (!api) {
      this._onError?.({ code: 'NO_ELECTRON', message: 'Not in Electron environment', recoverable: false });
      return;
    }

    this._setState('requesting');

    try {
      // Register system audio chunk receiver
      const unsub1 = api.audio.onSystemAudio((chunk: ArrayBuffer) => {
        if (this._state === 'capturing') {
          this._onChunk?.(chunk);
        }
      });
      this._systemUnsubscribers.push(unsub1);

      // Register error receiver
      const unsub2 = api.audio.onSystemAudioError((msg: string) => {
        this._onError?.({ code: 'SYSTEM_AUDIO', message: msg, recoverable: true });
      });
      this._systemUnsubscribers.push(unsub2);

      // Start capture in main process
      await api.audio.startSystemCapture(deviceId ?? null);
      this._setState('capturing');
    } catch (err) {
      this._setState('error');
      this._onError?.({
        code: 'SYSTEM_AUDIO_START',
        message: `Failed to start system audio: ${(err as Error).message}`,
        recoverable: true,
      });
    }
  }

  private async _stopSystemAudio(): Promise<void> {
    const api = window.electronAPI;
    if (api) {
      try {
        await api.audio.stopSystemCapture();
      } catch { /* ignore */ }
    }
    // Clean up IPC listeners
    for (const unsub of this._systemUnsubscribers) {
      try { unsub(); } catch { /* ignore */ }
    }
    this._systemUnsubscribers = [];
  }

  // ── Helpers ────────────────────────────────────────────────

  private _setState(state: AudioCaptureState): void {
    this._state = state;
    this._onStateChange?.(state);
  }
}


// ── Utility ────────────────────────────────────────────────────

/**
 * Convert Float32Array audio samples [-1, +1] to Int16Array PCM.
 * This is the format expected by the ASR backend.
 */
function float32ToInt16(float32: Float32Array): Int16Array {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return int16;
}

/** Singleton instance shared across the app. */
export const audioCapture = new AudioCaptureService();
