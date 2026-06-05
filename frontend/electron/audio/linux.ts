/**
 * Linux system audio capture implementation (STUB).
 *
 * Linux audio capture strategy:
 *   - PulseAudio: The dominant sound server on Linux desktops.
 *     Use `parec` (PulseAudio Record) to capture monitor source output.
 *     Command: parec --format=s16le --rate=16000 --channels=1 -d <monitor_source>
 *   - PipeWire: The modern replacement for PulseAudio (Ubuntu 22.10+).
 *     Use `pw-record` or pipewire-pulse compatibility layer.
 *     Command: pw-record --format=s16 --rate=16000 --channels=1 --target=<node_id> -
 *
 * Recommended approach:
 *   1. Detect if PulseAudio or PipeWire is running.
 *   2. Enumerate monitor sources via `pactl list sources` or `pw-cli list-objects`.
 *   3. Spawn `parec` or `pw-record` as a child process, reading PCM from stdout.
 *   4. The '-' argument outputs to stdout (raw PCM stream).
 *
 * PulseAudio monitor source naming convention:
 *   - Default monitor: <sink_name>.monitor (e.g., alsa_output.pci-0000_00_1f.3.analog-stereo.monitor)
 *   - User can select via `pactl list short sources | grep monitor`
 *
 * Implementation plan (commit 3):
 *   - Detect audio system (PA vs PW).
 *   - Enumerate monitor sources programmatically.
 *   - Spawn recording subprocess and pipe to audio pipeline.
 */
import type { SystemAudioCapturer, SystemAudioDeviceInfo, AudioChunkCallback, AudioErrorCallback } from './types';

export class LinuxAudioCapturer implements SystemAudioCapturer {
  private pulseAvailable = false;
  private pipewireAvailable = false;

  isSupported(): boolean {
    // Will check for PulseAudio/PipeWire in commit 3
    return this.pulseAvailable || this.pipewireAvailable;
  }

  async listDevices(): Promise<SystemAudioDeviceInfo[]> {
    // Placeholder — implemented in commit 3
    return [{
      id: 'default',
      name: '默认音频输出 (PulseAudio/PipeWire)',
      isDefault: true,
      isLoopback: true,
    }];
  }

  async start(
    _deviceId: string | null,
    _onChunk: AudioChunkCallback,
    onError: AudioErrorCallback,
  ): Promise<void> {
    onError(new Error('Linux system audio capture not yet implemented'));
  }

  async stop(): Promise<void> {
    // no-op
  }
}
