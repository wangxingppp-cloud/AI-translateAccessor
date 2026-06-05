/**
 * Internal types for OS-specific audio capture implementations.
 *
 * Each platform module (windows.ts, macos.ts, linux.ts) implements
 * the SystemAudioCapturer interface.
 */

/** Callback receiving raw PCM chunks from system audio capture. */
export type AudioChunkCallback = (chunk: Buffer) => void;

/** Error callback with platform-specific details. */
export type AudioErrorCallback = (error: Error) => void;

/**
 * Interface that every OS-specific system audio capturer must implement.
 *
 * The Electron main process creates ONE capturer per platform,
 * then pipes the PCM chunks to the renderer via IPC.
 */
export interface SystemAudioCapturer {
  /** List available system audio output devices. */
  listDevices(): Promise<SystemAudioDeviceInfo[]>;

  /**
   * Start capturing system audio output.
   *
   * @param deviceId  Target output device (empty = default).
   * @param onChunk   Called with each PCM chunk (16kHz, 16bit, mono).
   * @param onError   Called on non-recoverable errors.
   */
  start(
    deviceId: string | null,
    onChunk: AudioChunkCallback,
    onError: AudioErrorCallback,
  ): Promise<void>;

  /** Stop capturing and release resources. */
  stop(): Promise<void>;

  /** Whether this platform supports system audio loopback. */
  isSupported(): boolean;
}

/** Audio device info returned by listDevices(). */
export interface SystemAudioDeviceInfo {
  id: string;
  name: string;
  isDefault: boolean;
  isLoopback: boolean;
}
