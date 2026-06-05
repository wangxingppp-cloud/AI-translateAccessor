/**
 * macOS system audio capture implementation (STUB).
 *
 * macOS audio capture strategy:
 *   - CoreAudio: The native audio API on macOS.
 *   - BlackHole: An open-source virtual audio loopback driver.
 *     User installs BlackHole once, then routes system audio through it.
 *   - ScreenCaptureKit (macOS 12.3+): Can capture app-specific audio
 *     without a virtual driver, but limited to specific apps, not system-wide.
 *
 * Recommended approach:
 *   1. Primary: BlackHole virtual driver + CoreAudio capture.
 *      - User installs BlackHole from https://github.com/ExistentialAudio/BlackHole
 *      - Creates a Multi-Output Device (system audio → BlackHole + speakers).
 *      - Our app reads from BlackHole's input stream.
 *   2. Fallback: ScreenCaptureKit for app-specific capture.
 *   3. Fallback: sox or ffmpeg with Soundflower.
 *
 * Implementation plan (commit 2):
 *   - Use a small Swift/Rust helper binary to interface with CoreAudio.
 *   - Spawn it as a child process, reading PCM from stdout.
 *   - Or use the `node-core-audio` native addon (if maintained).
 */
import type { SystemAudioCapturer, SystemAudioDeviceInfo, AudioChunkCallback, AudioErrorCallback } from './types';

export class MacOSAudioCapturer implements SystemAudioCapturer {
  private isAvailable = false;

  isSupported(): boolean {
    // Check if BlackHole or similar loopback device is installed
    // Will be properly implemented in commit 2
    return this.isAvailable;
  }

  async listDevices(): Promise<SystemAudioDeviceInfo[]> {
    // Placeholder — implemented in commit 2
    return [{
      id: 'blackhole',
      name: 'BlackHole (需安装)',
      isDefault: true,
      isLoopback: true,
    }];
  }

  async start(
    _deviceId: string | null,
    _onChunk: AudioChunkCallback,
    onError: AudioErrorCallback,
  ): Promise<void> {
    onError(new Error('macOS system audio capture not yet implemented'));
  }

  async stop(): Promise<void> {
    // no-op
  }
}
