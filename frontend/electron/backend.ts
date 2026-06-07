/**
 * Python backend process manager.
 *
 * Spawns the FastAPI backend as a child process, discovers the port
 * from stdout, and manages its lifecycle (start, stop, restart).
 *
 * Dev mode:   `python -m app.main`            (reads PORT from .env)
 * Prod mode:  `ai-translate-backend.exe`       (PyInstaller bundled)
 */
import { spawn, ChildProcess } from 'child_process';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';
import { app } from 'electron';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

let backendProcess: ChildProcess | null = null;
let backendPort: number | null = null;
let onReady: ((port: number) => void) | null = null;
let onError: ((msg: string) => void) | null = null;

export function setBackendCallbacks(
  ready: (port: number) => void,
  error: (msg: string) => void,
) {
  onReady = ready;
  onError = error;
  // If port already discovered, notify immediately
  if (backendPort) ready(backendPort);
}

export function getBackendPort(): number | null {
  return backendPort;
}

export async function startBackend(): Promise<void> {
  if (backendProcess && backendPort) return; // Already running

  const cmd = findBackendCommand();
  const args = findBackendArgs(cmd);

  console.log(`[backend] Starting: ${cmd} ${args.join(' ')}`);

  backendProcess = spawn(cmd, args, {
    stdio: ['pipe', 'pipe', 'pipe'],
    cwd: findBackendCwd(),
    env: {
      ...process.env,
      PORT: '0', // OS auto-assign port
      MODELS_DIR: findModelsDir(), // Tell backend where models are
    },
  });

  let stdoutBuffer = '';
  let stderrBuffer = '';

  backendProcess.stdout!.on('data', (chunk: Buffer) => {
    stdoutBuffer += chunk.toString();

    // Look for the ready line
    const lines = stdoutBuffer.split('\n');
    for (const line of lines) {
      const match = line.match(/^AI_TRANSLATE_READY port=(\d+)/);
      if (match) {
        backendPort = parseInt(match[1], 10);
        console.log(`[backend] Ready on port ${backendPort}`);
        onReady?.(backendPort);
      }
    }
    // Keep only the last incomplete line
    const lastNewline = stdoutBuffer.lastIndexOf('\n');
    if (lastNewline >= 0) {
      stdoutBuffer = stdoutBuffer.slice(lastNewline + 1);
    }
  });

  backendProcess.stderr!.on('data', (chunk: Buffer) => {
    stderrBuffer += chunk.toString();
  });

  backendProcess.on('error', (err) => {
    const msg = `Backend process error: ${err.message}`;
    console.error(`[backend] ${msg}`);
    onError?.(msg);
  });

  backendProcess.on('close', (code) => {
    console.log(`[backend] Exited with code ${code}`);
    if (code !== 0 && code !== null) {
      const msg = `Backend crashed (exit ${code}).\n${stderrBuffer.slice(-500)}`;
      onError?.(msg);
    }
    backendProcess = null;
    backendPort = null;
  });
}

export function stopBackend(): void {
  if (backendProcess) {
    console.log('[backend] Stopping...');
    try { backendProcess.kill('SIGTERM'); } catch { /* ignore */ }
    backendProcess = null;
    backendPort = null;
  }
}

// ── Path resolution ────────────────────────────────────────────

function findBackendCwd(): string {
  // Dev: __dirname = dist-electron/ → backend is at ../../backend
  const devPath = join(__dirname, '..', '..', 'backend');
  if (existsSync(join(devPath, 'app', 'main.py'))) return devPath;

  // Prod: <app>/resources/backend/
  const prodPath = join(process.resourcesPath ?? '', 'backend');
  if (existsSync(join(prodPath, 'app', 'main.py'))) return prodPath;

  // Bundled .exe doesn't need cwd
  return __dirname;
}

function findModelsDir(): string {
  // Dev: __dirname = dist-electron/ → models is at ../../models
  const devPath = join(__dirname, '..', '..', 'models');
  if (existsSync(devPath)) return devPath;

  // Prod: <app>/resources/models/
  const prodPath = join(process.resourcesPath ?? '', 'models');
  if (existsSync(prodPath)) return prodPath;

  return '';
}

function findBackendCommand(): string {
  // Production: bundled PyInstaller exe
  const prodExe = join(process.resourcesPath ?? '', 'backend', 'ai-translate-backend.exe');
  if (existsSync(prodExe)) return prodExe;

  // Development: find Python
  const pythonCommands = [
    join(findBackendCwd(), 'venv', 'Scripts', 'python.exe'),
    'python', 'python3', 'py',
  ];
  for (const py of pythonCommands) {
    try {
      const { execSync } = require('child_process');
      execSync(`"${py}" --version`, { stdio: 'ignore', timeout: 3000 });
      return py;
    } catch { /* try next */ }
  }

  throw new Error('Python not found. Install Python 3.11+ or check PATH.');
}

function findBackendArgs(cmd: string): string[] {
  // Bundled backend .exe (PyInstaller): no args needed
  if (cmd.includes('ai-translate-backend')) return [];

  // Python interpreter: run module
  return ['-m', 'app.main'];
}
