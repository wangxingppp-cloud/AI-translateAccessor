/**
 * Audio capture types.
 *
 * Audio flows through this pipeline:
 *   AudioSource → PCM chunks (16kHz, 16bit, mono) → WebSocket → Python backend
 *
 * Two capture modes:
 *   1. Microphone  — Web Audio API in renderer (cross-platform, no IPC)
 *   2. System      — OS-specific native capture in main process (via IPC)
 */

/** Audio source selection. */
export type AudioSource = 'microphone' | 'system';

/** Standard audio format for ASR input. */
export interface AudioFormat {
  sampleRate: 16000;
  channels: 1;
  bitsPerSample: 16;
  /** Duration of each chunk in milliseconds. */
  chunkMs: 200;
  /** Number of PCM samples per chunk (sampleRate * chunkMs / 1000). */
  chunkSamples: 3200;
  /** Number of bytes per chunk (chunkSamples * channels * bitsPerSample / 8). */
  chunkBytes: 6400;
}

/** Default audio format constants. */
export const AUDIO_FORMAT: AudioFormat = {
  sampleRate: 16000,
  channels: 1,
  bitsPerSample: 16,
  chunkMs: 200,
  chunkSamples: 3200,
  chunkBytes: 6400,
};

/** Audio capture configuration. */
export interface AudioCaptureConfig {
  source: AudioSource;
  format: AudioFormat;
  /** Target device ID for microphone capture (empty = default). */
  deviceId?: string;
}

/** System audio device information. */
export interface SystemAudioDevice {
  id: string;
  name: string;
  isDefault: boolean;
  isLoopback: boolean;       // Supports loopback capture
  platform: NodeJS.Platform;
}

/** State of the audio capture pipeline. */
export type AudioCaptureState =
  | 'idle'
  | 'requesting'   // Asking for permissions
  | 'capturing'    // Actively streaming audio
  | 'error';

/** Error details from audio capture. */
export interface AudioCaptureError {
  code: string;
  message: string;
  recoverable: boolean;
}
