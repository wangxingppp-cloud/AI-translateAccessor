import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// ESM-compatible __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// The built directory structure
//
// ├─┬─ dist-electron
// │ ├── main.js
// │ └── preload.js
// ├─┬─ dist
// │ └── index.html
//
process.env.DIST = path.join(__dirname, '../dist');
process.env.VITE_PUBLIC = app.isPackaged
  ? process.env.DIST
  : path.join(process.env.DIST, '../public');

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
}

let mainWindow: BrowserWindow | null = null;

// Handle second instance — focus existing window
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL'];

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 670,
    minWidth: 600,
    minHeight: 400,
    frame: false,
    titleBarStyle: 'hidden',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.on('maximize', () => mainWindow?.webContents.send('window-maximized', true));
  mainWindow.on('unmaximize', () => mainWindow?.webContents.send('window-maximized', false));

  if (VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(VITE_DEV_SERVER_URL);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(process.env.DIST!, 'index.html'));
  }
}

// ── IPC Handlers ──────────────────────────────────────────────

function registerWindowIPC() {
  ipcMain.on('window:minimize', () => mainWindow?.minimize());
  ipcMain.on('window:maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
  });
  ipcMain.on('window:close', () => mainWindow?.close());
  ipcMain.handle('window:isMaximized', () => mainWindow?.isMaximized() ?? false);

  ipcMain.handle('app:getVersion', () => app.getVersion());
  ipcMain.handle('app:getPlatform', () => process.platform);
}

// ── App lifecycle ────────────────────────────────────────────

app.whenReady().then(() => {
  registerWindowIPC();

  // Register audio IPC (wrapped in try/catch so a missing native module
  // doesn't prevent the window from opening)
  try {
    // Use dynamic import for ESM compatibility
    import('./ipc/audio.js').then(({ registerAudioIPC }) => {
      if (mainWindow) {
        registerAudioIPC(mainWindow);
      }
    }).catch((err) => {
      console.error('Audio IPC registration failed (non-fatal):', err.message);
    });
  } catch (err) {
    console.error('Audio IPC import failed (non-fatal):', err);
  }

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
