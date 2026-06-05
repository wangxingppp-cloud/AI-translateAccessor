/**
 * Audio IPC channel registration.
 *
 * Registers handlers in the Electron main process for audio operations.
 * The renderer invokes these via the preload-exposed electronAPI.audio.*.
 */
import { ipcMain, BrowserWindow } from 'electron';
import { createSystemAudioCapturer } from '../audio';

let capturer: Awaited<ReturnType<typeof createSystemAudioCapturer>> | null = null;

export function registerAudioIPC(mainWindow: BrowserWindow): void {
  // ── List audio devices ──────────────────────────────────────
  ipcMain.handle('audio:listDevices', async () => {
    if (!capturer) {
      capturer = createSystemAudioCapturer();
    }
    return capturer.listDevices();
  });

  // ── Start system audio capture ──────────────────────────────
  ipcMain.handle('audio:startSystemCapture', async (_event, deviceId: string | null) => {
    if (!capturer) {
      capturer = createSystemAudioCapturer();
    }

    if (!capturer.isSupported()) {
      throw new Error('System audio capture is not supported on this platform');
    }

    await capturer.start(
      deviceId,
      (chunk: Buffer) => {
        // Forward PCM chunks to renderer
        mainWindow.webContents.send('audio:system-chunk', chunk);
      },
      (error: Error) => {
        mainWindow.webContents.send('audio:system-error', error.message);
      },
    );

    return { success: true };
  });

  // ── Stop system audio capture ───────────────────────────────
  ipcMain.handle('audio:stopSystemCapture', async () => {
    if (capturer) {
      await capturer.stop();
    }
    return { success: true };
  });
}
