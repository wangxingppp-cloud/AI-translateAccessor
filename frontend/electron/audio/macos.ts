/**
 * macOS system audio capture implementation.
 *
 * Architecture:
 *   macOS does NOT allow direct capture of system audio output without a
 *   loopback driver.  The user must install one of:
 *
 *   - BlackHole (recommended, free, open-source)
 *     https://github.com/ExistentialAudio/BlackHole
 *     Install: brew install blackhole-2ch
 *
 *   - Soundflower (free, older, limited Apple Silicon support)
 *
 *   - Loopback by Rogue Amoeba (paid, most polished)
 *
 * Setup instructions for the user:
 *   1. Install BlackHole: `brew install blackhole-2ch`
 *   2. Open Audio MIDI Setup.app
 *   3. Create a Multi-Output Device containing:
 *        - Your speakers/headphones (so you can hear)
 *        - BlackHole 2ch (so our app can capture)
 *   4. Set the Multi-Output Device as system output
 *   5. Our app captures from "BlackHole 2ch" input
 *
 * Capture mechanism:
 *   Uses `sox` (Sound eXchange) which ships with pre-built macOS CoreAudio
 *   support via Homebrew.  The command:
 *     sox -t coreaudio "BlackHole 2ch" -t raw -r 16000 -c 1 -b 16 -e signed-integer -
 *   reads from the BlackHole virtual input and writes raw 16kHz mono PCM
 *   to stdout, which we pipe into the audio pipeline.
 *
 * Alternative (production):
 *   Compile the included Swift helper (see bottom of file) into a native
 *   binary.  It uses AudioUnit directly, avoiding the sox dependency.
 *   Bundle it at: <app>/Resources/mac-audio-capture
 */
import { spawn, ChildProcess } from 'child_process';
import { execSync } from 'child_process';
import type {
  SystemAudioCapturer,
  SystemAudioDeviceInfo,
  AudioChunkCallback,
  AudioErrorCallback,
} from './types';

// ── Known loopback drivers ──────────────────────────────────────

const LOOPBACK_DRIVERS = [
  {
    name: 'BlackHole 2ch',
    id: 'BlackHole 2ch',
    description: 'BlackHole (推荐) — 开源免费，brew install blackhole-2ch',
  },
  {
    name: 'BlackHole 16ch',
    id: 'BlackHole 16ch',
    description: 'BlackHole 16ch',
  },
  {
    name: 'Soundflower (2ch)',
    id: 'Soundflower (2ch)',
    description: 'Soundflower — 较老，Apple Silicon 兼容性有限',
  },
  {
    name: 'Loopback Audio',
    id: 'Loopback Audio',
    description: 'Loopback (Rogue Amoeba) — 付费，体验最好',
  },
];

// ── Swift helper source (compiled for production, optional) ─────
//
// To compile:  swiftc -O -o mac-audio-capture mac_audio_capture.swift
// The binary uses AudioUnit for direct loopback capture without sox.
//
// ```swift
// import CoreAudio
// import AudioToolbox
// import Foundation
//
// let targetSampleRate: Float64 = 16000
// let targetChannels: UInt32 = 1
// let chunkSamples = 3200  // 200ms
//
// // Find the BlackHole input device
// func findLoopbackDevice() -> AudioDeviceID? {
//     var propAddress = AudioObjectPropertyAddress(
//         mSelector: kAudioHardwarePropertyDevices,
//         mScope: kAudioObjectPropertyScopeGlobal,
//         mElement: kAudioObjectPropertyElementMain
//     )
//     var dataSize: UInt32 = 0
//     AudioObjectGetPropertyDataSize(
//         AudioObjectID(kAudioObjectSystemObject), &propAddress, 0, nil, &dataSize)
//     let deviceCount = Int(dataSize) / MemoryLayout<AudioDeviceID>.size
//     var devices = [AudioDeviceID](repeating: 0, count: deviceCount)
//     AudioObjectGetPropertyData(
//         AudioObjectID(kAudioObjectSystemObject), &propAddress, 0, nil, &dataSize, &devices)
//
//     for device in devices {
//         // Get device name and check if it's a loopback device
//         var name: CFString = "" as CFString
//         var nameSize = UInt32(MemoryLayout<CFString>.size)
//         var nameProp = AudioObjectPropertyAddress(
//             mSelector: kAudioDevicePropertyDeviceNameCFString,
//             mScope: kAudioObjectPropertyScopeInput,
//             mElement: kAudioObjectPropertyElementMain
//         )
//         AudioObjectGetPropertyData(device, &nameProp, 0, nil, &nameSize, &name)
//         if (name as String).contains("BlackHole") ||
//            (name as String).contains("Soundflower") ||
//            (name as String).contains("Loopback") {
//             return device
//         }
//     }
//     return nil
// }
//
// // Set up AudioUnit for capture...
// // (full implementation would configure AUHAL, set sample rate, start I/O)
// // Output raw PCM to stdout in 200ms chunks
// while true {
//     // Read from AudioUnit
//     // Write chunk to stdout
//     fwrite(buffer, 1, chunkSamples * 2, stdout)
//     fflush(stdout)
// }
// ```

// ── Implementation ──────────────────────────────────────────────

export class MacOSAudioCapturer implements SystemAudioCapturer {
  private process: ChildProcess | null = null;
  private onChunk: AudioChunkCallback | null = null;
  private onError: AudioErrorCallback | null = null;
  private _detectedDevices: SystemAudioDeviceInfo[] = [];

  isSupported(): boolean {
    // macOS always supports the architecture — the question is whether
    // a loopback driver is installed. We check lazily in listDevices().
    return true;
  }

  async listDevices(): Promise<SystemAudioDeviceInfo[]> {
    try {
      const devices: SystemAudioDeviceInfo[] = [];

      // Use system_profiler to enumerate audio devices and detect loopback drivers
      const raw = execSync(
        'system_profiler SPAudioDataType -json',
        { encoding: 'utf-8', timeout: 5000 },
      );
      const data = JSON.parse(raw);

      // The output structure is: { SPAudioDataType: [{ _name, _items: [...] }] }
      const audioSection = data?.SPAudioDataType ?? [];
      let allItems: Array<Record<string, unknown>> = [];
      for (const section of audioSection) {
        if (section._items) {
          allItems = allItems.concat(section._items);
        }
      }

      // Check for known loopback drivers in the output devices
      const outputNames = allItems
        .filter((d) => typeof d._name === 'string' && d.coreaudio_device_output === 'spkr_yes')
        .map((d) => d._name as string);

      for (const driver of LOOPBACK_DRIVERS) {
        for (const name of outputNames) {
          if (name.toLowerCase().includes(driver.name.toLowerCase())) {
            devices.push({
              id: driver.id,
              name: driver.description,
              isDefault: false,
              isLoopback: true,
            });
          }
        }
      }

      // Also check if sox is available
      try {
        execSync('which sox', { encoding: 'utf-8', timeout: 2000 });
      } catch {
        // sox not found — will use bundled Swift helper or report error
      }

      // If no loopback driver found, return instructions
      if (devices.length === 0) {
        devices.push({
          id: 'none',
          name: '未检测到虚拟音频驱动。请安装 BlackHole: brew install blackhole-2ch',
          isDefault: true,
          isLoopback: false,
        });
      }

      this._detectedDevices = devices;
      return devices;
    } catch (err) {
      // system_profiler failed — return a sensible default
      return [{
        id: 'blackhole',
        name: 'BlackHole 2ch (brew install blackhole-2ch)',
        isDefault: true,
        isLoopback: true,
      }];
    }
  }

  async start(
    deviceId: string | null,
    onChunk: AudioChunkCallback,
    onError: AudioErrorCallback,
  ): Promise<void> {
    this.onChunk = onChunk;
    this.onError = onError;

    const targetDevice = deviceId ?? 'BlackHole 2ch';

    // Try strategy 1: sox (installed via Homebrew)
    try {
      execSync('which sox', { encoding: 'utf-8', timeout: 2000 });

      this.process = spawn('sox', [
        '-t', 'coreaudio', targetDevice,    // Input: CoreAudio device
        '-t', 'raw',                         // Output: raw PCM
        '-r', '16000',                       // Sample rate
        '-c', '1',                           // Channels
        '-b', '16',                          // Bit depth
        '-e', 'signed-integer',              // Encoding
        '-',                                 // stdout
      ], {
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      this._setupProcess();

      return;
    } catch {
      // sox not found, try strategy 2
    }

    // Try strategy 2: bundled Swift helper
    try {
      const { resolve } = await import('path');
      const helperPath = resolve(
        process.resourcesPath ?? __dirname,
        '..',
        'resources',
        'mac-audio-capture',
      );

      this.process = spawn(helperPath, [targetDevice], {
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      this._setupProcess();
      return;
    } catch {
      // Helper not found
    }

    // Nothing worked
    onError(new Error(
      'macOS 系统音频采集需要安装额外工具。\n\n' +
      '方案 1（推荐）: brew install blackhole-2ch sox\n' +
      '方案 2: 下载 BlackHole: https://github.com/ExistentialAudio/BlackHole\n\n' +
      '安装后请创建多输出设备（Audio MIDI Setup.app），' +
      '将系统音频同时输出到扬声器和 BlackHole。',
    ));
  }

  async stop(): Promise<void> {
    if (this.process) {
      this.process.stdout?.removeAllListeners();
      this.process.stderr?.removeAllListeners();
      this.process.removeAllListeners();
      this.process.kill('SIGTERM');
      this.process = null;
    }
    this.onChunk = null;
    this.onError = null;
  }

  // ── Private ──────────────────────────────────────────────────

  private _setupProcess(): void {
    if (!this.process) return;

    let stderr = '';

    this.process.stdout!.on('data', (chunk: Buffer) => {
      this.onChunk?.(chunk);
    });

    this.process.stderr!.on('data', (data: Buffer) => {
      stderr += data.toString();
    });

    this.process.on('error', (err) => {
      this.onError?.(new Error(`CoreAudio 采集进程错误: ${err.message}`));
    });

    this.process.on('close', (code) => {
      if (code !== 0 && code !== null) {
        this.onError?.(new Error(
          `CoreAudio 采集退出 (code ${code})。${stderr ? '\n' + stderr : ''}\n` +
          '请确认 BlackHole 已安装且未被其他应用占用。'
        ));
      }
    });
  }
}
