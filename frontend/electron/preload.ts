import { contextBridge, ipcRenderer } from 'electron';

/**
 * Expose protected APIs to the renderer process via contextBridge.
 * This keeps the renderer sandboxed while allowing controlled IPC access.
 */
const electronAPI = {
  // ── Window controls ────────────────────────────────────────
  window: {
    minimize: () => ipcRenderer.send('window:minimize'),
    maximize: () => ipcRenderer.send('window:maximize'),
    close: () => ipcRenderer.send('window:close'),
    isMaximized: (): Promise<boolean> => ipcRenderer.invoke('window:isMaximized'),
    onMaximizedChange: (callback: (maximized: boolean) => void) => {
      ipcRenderer.on('window-maximized', (_event, maximized) => callback(maximized));
    },
  },

  // ── App info ───────────────────────────────────────────────
  app: {
    getVersion: (): Promise<string> => ipcRenderer.invoke('app:getVersion'),
    getPlatform: (): Promise<NodeJS.Platform> => ipcRenderer.invoke('app:getPlatform'),
  },
};

contextBridge.exposeInMainWorld('electronAPI', electronAPI);

// Type declaration for the renderer process
export type ElectronAPI = typeof electronAPI;
