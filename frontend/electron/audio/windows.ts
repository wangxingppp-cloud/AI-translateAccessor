/**
 * Windows system audio capture via NAudio (pre-compiled .exe).
 *
 * The helper binary is built from `resources/wasapi-capture/` using:
 *   dotnet publish -c Release -o ./publish
 *
 * It uses NAudio's WasapiLoopbackCapture + MediaFoundationResampler
 * to capture system audio output and write 16kHz mono 16-bit PCM to stdout.
 *
 * The binary and its DLLs are bundled as Electron extraResources at build time.
 */
import { spawn, ChildProcess } from 'child_process';
import { join, dirname } from 'path';
import { existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { app } from 'electron';
import type {
  SystemAudioCapturer,
  SystemAudioDeviceInfo,
  AudioChunkCallback,
  AudioErrorCallback,
} from './types';

// ESM-compatible __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function findHelper(): string {
  // Dev: __dirname = dist-electron/ → ../resources/wasapi-capture-bin/
  // Prod: process.resourcesPath/wasapi-capture/

  const devPath = join(__dirname, '..', 'resources', 'wasapi-capture-bin', 'wasapi-capture.exe');
  const prodPath = join(
    (process as any).resourcesPath ?? __dirname,
    'wasapi-capture',
    'wasapi-capture.exe',
  );

  if (existsSync(devPath) && !app.isPackaged) {
    return devPath;
  }
  if (existsSync(prodPath)) {
    return prodPath;
  }

  throw new Error(
    `WASAPI 捕获助手未找到。\n` +
    `开发: cd resources/wasapi-capture && dotnet publish -c Release -o publish\n` +
    `生产: 确保 wasapi-capture.exe 打包在 extraResources 中`
  );
}

export class WindowsAudioCapturer implements SystemAudioCapturer {
  private process: ChildProcess | null = null;
  private onChunk: AudioChunkCallback | null = null;
  private onError: AudioErrorCallback | null = null;

  isSupported(): boolean { return true; }

  async listDevices(): Promise<SystemAudioDeviceInfo[]> {
    return [{
      id: 'default',
      name: '默认播放设备 (WASAPI Loopback)',
      isDefault: true,
      isLoopback: true,
    }];
  }

  async start(
    _deviceId: string | null,
    onChunk: AudioChunkCallback,
    onError: AudioErrorCallback,
  ): Promise<void> {
    this.onChunk = onChunk;
    this.onError = onError;

    try {
      const exePath = findHelper();

      this.process = spawn(exePath, [], {
        stdio: ['pipe', 'pipe', 'pipe'],
        windowsHide: true,
        cwd: join(exePath, '..'), // DLLs are next to the exe
      });

      let stderr = '';

      this.process.stdout!.on('data', (chunk: Buffer) => {
        this.onChunk?.(chunk);
      });

      this.process.stderr!.on('data', (data: Buffer) => {
        stderr += data.toString();
      });

      this.process.on('error', (err) => {
        this.onError?.(new Error(`WASAPI 助手启动失败: ${err.message}`));
      });

      this.process.on('close', (code) => {
        if (code !== 0 && code !== null) {
          this.onError?.(new Error(
            (stderr || `WASAPI 退出码 ${code}。\n`) +
            '请确认:\n' +
            '  1. Windows 音频服务正在运行\n' +
            '  2. 至少有一个活动播放设备'
          ));
        }
      });
    } catch (err) {
      onError(new Error(`WASAPI 启动失败: ${(err as Error).message}`));
    }
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
