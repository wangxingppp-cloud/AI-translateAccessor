/**
 * Preload script — CommonJS format (Electron sandbox requires CJS).
 *
 * This file is NOT processed by Vite/TypeScript. It is copied directly
 * to dist-electron/ and loaded by the main process.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // ── Window controls ────────────────────────────────────────
  window: {
    minimize: function () { ipcRenderer.send('window:minimize'); },
    maximize: function () { ipcRenderer.send('window:maximize'); },
    close: function () { ipcRenderer.send('window:close'); },
    isMaximized: function () { return ipcRenderer.invoke('window:isMaximized'); },
    onMaximizedChange: function (callback) {
      ipcRenderer.on('window-maximized', function (_event, maximized) { callback(maximized); });
    },
  },

  // ── App info ───────────────────────────────────────────────
  app: {
    getVersion: function () { return ipcRenderer.invoke('app:getVersion'); },
    getPlatform: function () { return ipcRenderer.invoke('app:getPlatform'); },
  },

  // ── Audio ──────────────────────────────────────────────────
  audio: {
    listDevices: function () { return ipcRenderer.invoke('audio:listDevices'); },
    startSystemCapture: function (deviceId) { return ipcRenderer.invoke('audio:startSystemCapture', deviceId); },
    stopSystemCapture: function () { return ipcRenderer.invoke('audio:stopSystemCapture'); },
    onSystemAudio: function (callback) {
      var handler = function (_event, chunk) { callback(chunk); };
      ipcRenderer.on('audio:system-chunk', handler);
      return function () { ipcRenderer.removeListener('audio:system-chunk', handler); };
    },
    onSystemAudioError: function (callback) {
      var handler = function (_event, msg) { callback(msg); };
      ipcRenderer.on('audio:system-error', handler);
      return function () { ipcRenderer.removeListener('audio:system-error', handler); };
    },
  },
});
