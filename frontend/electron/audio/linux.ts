/**
 * Linux system audio capture implementation.
 *
 * Linux audio architecture:
 *   - PulseAudio: Traditional sound server (Ubuntu < 22.04, Debian, Fedora < 34)
 *   - PipeWire: Modern replacement (Ubuntu 22.04+, Fedora 34+, Arch)
 *   - ALSA: Kernel-level API (bare fallback, no software mixing)
 *
 * Detection order:
 *   1. Check for `pactl` (works with both PA and PW via pipewire-pulse)
 *   2. Check for `pw-cli` (PipeWire native)
 *   3. Fall back to `arecord` (ALSA)
 *
 * Capture approach:
 *   - PulseAudio/PipeWire: Read from the monitor source (sink_name.monitor)
 *     which captures everything playing through that output device.
 *   - Command: parec --format=s16le --rate=16000 --channels=1
 *   - PipeWire native: pw-record --format=s16 --rate=16000 --channels=1 -
 *   - ALSA: arecord -f S16_LE -r 16000 -c 1 -t raw
 *
 * The spawned process writes raw 16-bit PCM (16kHz mono) to stdout.
 */
import { spawn, ChildProcess, execSync } from 'child_process';
import type {
  SystemAudioCapturer,
  SystemAudioDeviceInfo,
  AudioChunkCallback,
  AudioErrorCallback,
} from './types';

// ── Detection helpers ──────────────────────────────────────────

interface AudioSystem {
  type: 'pulseaudio' | 'pipewire' | 'alsa';
  captureCmd: string[];
  listCmd: string[];
}

function detectAudioSystem(): AudioSystem | null {
  // 1. PulseAudio (also works through PipeWire's pulse compatibility layer)
  try {
    execSync('pactl info', { encoding: 'utf-8', timeout: 3000 });
    return {
      type: 'pulseaudio',
      captureCmd: ['parec', '--format=s16le', '--rate=16000', '--channels=1'],
      listCmd: ['pactl', 'list', 'short', 'sources'],
    };
  } catch { /* not available */ }

  // 2. PipeWire native
  try {
    execSync('pw-cli info', { encoding: 'utf-8', timeout: 3000 });
    return {
      type: 'pipewire',
      captureCmd: ['pw-record', '--format=s16', '--rate=16000', '--channels=1', '-'],
      listCmd: ['pw-cli', 'list-objects', 'PipeWire:Interface:Node'],
    };
  } catch { /* not available */ }

  // 3. ALSA fallback
  try {
    execSync('arecord --version', { encoding: 'utf-8', timeout: 3000 });
    return {
      type: 'alsa',
      captureCmd: ['arecord', '-f', 'S16_LE', '-r', '16000', '-c', '1', '-t', 'raw'],
      listCmd: ['arecord', '-L'],
    };
  } catch { /* not available */ }

  return null;
}

// ── Implementation ──────────────────────────────────────────────

export class LinuxAudioCapturer implements SystemAudioCapturer {
  private process: ChildProcess | null = null;
  private onChunk: AudioChunkCallback | null = null;
  private onError: AudioErrorCallback | null = null;
  private audioSystem: AudioSystem | null = null;
  private devices: SystemAudioDeviceInfo[] = [];

  isSupported(): boolean {
    if (!this.audioSystem) {
      this.audioSystem = detectAudioSystem();
    }
    return this.audioSystem !== null;
  }

  async listDevices(): Promise<SystemAudioDeviceInfo[]> {
    const system = this.audioSystem ?? detectAudioSystem();
    if (!system) {
      return [{
        id: 'none',
        name: '未检测到音频系统。请安装 PulseAudio 或 PipeWire。',
        isDefault: true,
        isLoopback: false,
      }];
    }

    const devices: SystemAudioDeviceInfo[] = [
      { id: 'default', name: '默认音频输出 (Monitor)', isDefault: true, isLoopback: true },
    ];

    try {
      if (system.type === 'pulseaudio') {
        // Parse `pactl list short sources` for monitor entries
        const raw = execSync('pactl list short sources', { encoding: 'utf-8', timeout: 3000 });
        const lines = raw.trim().split('\n');
        for (const line of lines) {
          // Format: <index>\t<name>\t<driver>\t<sample_rate>\t<channels>
          const parts = line.split('\t');
          if (parts.length >= 2 && parts[1].includes('.monitor')) {
            const name = parts[1];
            // Skip duplicates of the default
            if (name !== devices[0].id) {
              devices.push({
                id: name,
                name: `${name} (Monitor)`,
                isDefault: false,
                isLoopback: true,
              });
            }
          }
        }
      }
    } catch { /* use default only */ }

    this.devices = devices;
    return devices;
  }

  async start(
    deviceId: string | null,
    onChunk: AudioChunkCallback,
    onError: AudioErrorCallback,
  ): Promise<void> {
    this.onChunk = onChunk;
    this.onError = onError;

    const system = this.audioSystem ?? detectAudioSystem();

    if (!system) {
      onError(new Error(
        'Linux 系统音频采集需要 PulseAudio 或 PipeWire。\n' +
        '请安装: sudo apt install pulseaudio-utils  (或 pipwire)\n' +
        '或使用 ALSA: sudo apt install alsa-utils'
      ));
      return;
    }

    const args = [...system.captureCmd];

    // If a specific monitor device is selected, add -d flag (PulseAudio)
    if (deviceId && deviceId !== 'default' && system.type === 'pulseaudio') {
      args.push('-d', deviceId);
    }

    this.process = spawn(args[0], args.slice(1), {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stderr = '';

    this.process.stdout!.on('data', (chunk: Buffer) => {
      this.onChunk?.(chunk);
    });

    this.process.stderr!.on('data', (data: Buffer) => {
      stderr += data.toString();
    });

    this.process.on('error', (err) => {
      this.onError?.(new Error(
        `${args[0]} 未找到。请安装:\n` +
        '  sudo apt install pulseaudio-utils\n' +
        '  或 sudo apt install pipewire-audio'
      ));
    });

    this.process.on('close', (code) => {
      if (code !== 0 && code !== null) {
        this.onError?.(new Error(
          `${system.type} 采集退出 (code ${code})。${stderr ? '\n' + stderr : ''}\n` +
          '请确认:\n' +
          '  1. 音频服务正在运行 (systemctl --user status pulseaudio)\n' +
          '  2. 当前有音频正在播放'
        ));
      }
    });
  }

  async stop(): Promise<void> {
    if (this.process) {
      this.process.stdout?.removeAllListeners();
      this.process.stderr?.removeAllListeners();
      this.process.removeAllListeners();
      try { this.process.kill('SIGTERM'); } catch { /* ignore */ }
      this.process = null;
    }
    this.onChunk = null;
    this.onError = null;
  }
}
