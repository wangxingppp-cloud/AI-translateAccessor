/**
 * Platform-aware system audio capturer factory.
 *
 * Automatically selects the correct implementation based on process.platform.
 * Each platform module lives in its own file (windows.ts, macos.ts, linux.ts).
 */
import type { SystemAudioCapturer } from './types';

export function createSystemAudioCapturer(): SystemAudioCapturer {
  switch (process.platform) {
    case 'win32':
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const { WindowsAudioCapturer } = require('./windows');
      return new WindowsAudioCapturer();

    case 'darwin':
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const { MacOSAudioCapturer } = require('./macos');
      return new MacOSAudioCapturer();

    case 'linux':
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const { LinuxAudioCapturer } = require('./linux');
      return new LinuxAudioCapturer();

    default:
      throw new Error(`Unsupported platform: ${process.platform}`);
  }
}

export type { SystemAudioCapturer, SystemAudioDeviceInfo, AudioChunkCallback, AudioErrorCallback } from './types';
