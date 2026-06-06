export interface ElectronAPI {
  window: {
    minimize: () => void;
    maximize: () => void;
    close: () => void;
    isMaximized: () => Promise<boolean>;
    onMaximizedChange: (callback: (maximized: boolean) => void) => void;
  };
  app: {
    getVersion: () => Promise<string>;
    getPlatform: () => Promise<NodeJS.Platform>;
  };
  audio: {
    listDevices: () => Promise<SystemAudioDeviceInfo[]>;
    startSystemCapture: (deviceId: string | null) => Promise<{ success: boolean }>;
    stopSystemCapture: () => Promise<{ success: boolean }>;
    onSystemAudio: (callback: (chunk: ArrayBuffer) => void) => () => void;
    onSystemAudioError: (callback: (message: string) => void) => () => void;
  };
  backend: {
    getPort: () => Promise<number | null>;
    onReady: (callback: (port: number) => void) => void;
    onError: (callback: (msg: string) => void) => void;
  };
}

export interface SystemAudioDeviceInfo {
  id: string;
  name: string;
  isDefault: boolean;
  isLoopback: boolean;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
