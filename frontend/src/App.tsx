import { useState, useCallback, useRef, useEffect } from 'react';
import './App.css';
import { useAudioCapture } from './hooks/useAudioCapture';
import { AudioSourceSelector, AudioControls, AudioVisualizer } from './components/audio';
import { SettingsPanel } from './components/settings';
import { SubtitleList } from './components/subtitle';
import { useSettingsStore } from './stores/settingsStore';
import { useConnectionStore } from './stores/connectionStore';
import { useSubtitleStore } from './stores/subtitleStore';
import { HistoryPanel } from './components/history';
import { GlossaryManager } from './components/glossary';
import { WebSocketClient } from './services/websocket-client';
import type { AudioSource } from './types/audio';
import type { ServerMessage } from './types/ws-messages';

const DEFAULT_WS_PORT = 8000;
const win = window as { electronAPI?: { window: { minimize: () => void; maximize: () => void; close: () => void }; backend?: { getPort: () => Promise<number | null>; onReady: (cb: (p: number) => void) => void; onError: (cb: (m: string) => void) => void } } };
const api = win.electronAPI;

function App() {
  const [source, setSource] = useState<AudioSource>('microphone');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const [onTop, setOnTop] = useState(false);

  const wsRef = useRef<WebSocketClient | null>(null);
  const llm = useSettingsStore((s) => s.llm);
  const asr = useSettingsStore((s) => s.asr);
  const srcLang = useSettingsStore((s) => s.sourceLang);
  const tgtLang = useSettingsStore((s) => s.targetLang);
  const { wsState, backendPort, backendError, setWsState, setBackendPort, setBackendError } = useConnectionStore();
  const { entries, addEntry, correctEntry, clear: clearSubtitles } = useSubtitleStore();

  // Discover backend port from Electron
  useEffect(() => {
    if (api?.backend) {
      api.backend.getPort().then((port) => { if (port) setBackendPort(port); });
      api.backend.onReady((port) => setBackendPort(port));
      api.backend.onError((msg) => setBackendError(msg));
    }
    if (!api) setBackendPort(DEFAULT_WS_PORT);
    api?.window.isAlwaysOnTop().then(setOnTop);
  }, []);

  // Auto-connect WebSocket when port is known (kept alive across sessions)
  useEffect(() => {
    if (!backendPort) return;
    const url = `ws://127.0.0.1:${backendPort}/ws/translate`;
    const ws = new WebSocketClient({ url });
    ws.onStateChange(setWsState);
    ws.onMessage((msg: ServerMessage) => {
      console.log('[WS-IN]', msg.type, msg.type === 'subtitle_draft' ? (msg as any).original?.slice(0, 30) : '');
      if (msg.type === 'subtitle_draft') {
        const entry = { id: msg.sequence_id, original: msg.original, translated: msg.translated, isCorrected: false, timestamp: msg.timestamp };
        addEntry(entry);
        console.log('[WS-IN] addEntry done, total entries:', useSubtitleStore.getState().entries.length);
      } else if (msg.type === 'subtitle_corrected') {
        correctEntry(msg.sequence_id, msg.corrected_text, msg.diff ?? []);
      }
    });
    wsRef.current = ws;
    ws.connect();
    return () => { ws.disconnect(); };
  }, [backendPort]);

  // Audio capture — buffer ~200ms chunks for low-latency streaming
  const chunkBuf = useRef<ArrayBuffer[]>([]);
  const { state: audioState, startCapture, stopCapture, switchSource, error: audioError, clearError } = useAudioCapture({
    onChunk: (chunk) => {
      chunkBuf.current.push(chunk);
      // Send merged ~200ms (small chunks, backend handles buffering)
      if (chunkBuf.current.length >= 3) {
        const total = chunkBuf.current.reduce((s, c) => s + c.byteLength, 0);
        const merged = new Uint8Array(total);
        let off = 0;
        for (const c of chunkBuf.current) {
          merged.set(new Uint8Array(c), off);
          off += c.byteLength;
        }
        wsRef.current?.sendAudioChunk(merged.buffer);
        chunkBuf.current = [];
      }
    },
  });
  const isTranslating = audioState === 'capturing';

  const handleSourceChange = useCallback((s: AudioSource) => {
    setSource(s); if (isTranslating) switchSource(s);
  }, [isTranslating, switchSource]);

  const handleToggle = useCallback(async () => {
    const client = wsRef.current; if (!client) return;
    if (isTranslating) {
      client.sendControl({ type: 'stop' });
      await stopCapture();
      clearSubtitles();
    } else {
      client.sendControl({
        type: 'start',
        config: {
          source_lang: srcLang, target_lang: tgtLang, audio_source: source,
          enable_correction: llm.enabled,
          llm: { provider: llm.provider, apiKey: llm.apiKey, model: llm.model, baseUrl: llm.baseUrl, enabled: llm.enabled },
          asr: { provider: asr.provider, apiKey: asr.apiKey, apiSecret: asr.apiSecret, appId: "", baseUrl: asr.baseUrl },
        },
      });
      startCapture(source);
    }
  }, [isTranslating, stopCapture, startCapture, source, llm, asr, clearSubtitles]);

  return (
    <div className="app-container">
      <header className="title-bar">
        <div className="title-bar__drag-region"><span className="title-bar__title">AI 同声传译</span></div>
        <div className="title-bar__controls">
          <button type="button" className="title-bar__btn" onClick={() => api?.window.minimize()} aria-label="最小化">─</button>
          <button type="button" className="title-bar__btn" onClick={() => api?.window.maximize()} aria-label="最大化">□</button>
          <button type="button" className="title-bar__btn title-bar__btn--close" onClick={() => api?.window.close()} aria-label="关闭">✕</button>
        </div>
      </header>

      <main className="main-content">
        <div className="status-bar">
          <span className={`status-indicator ${wsState === 'connected' ? 'status-indicator--connected' : 'status-indicator--disconnected'}`}>
            {wsState === 'connected' ? '🟢 已连接' : wsState === 'connecting' || wsState === 'reconnecting' ? '🟡 连接中...' : '⚫ 未连接'}
          </span>
          <div className="status-bar__right">
            <AudioVisualizer state={audioState} />
            <span className="status-lang">{srcLang.toUpperCase()} → {tgtLang.toUpperCase()}</span>
            <button type="button" className="settings-gear" onClick={() => setHistoryOpen(true)} title="翻译历史">📋</button>
            <button type="button" className="settings-gear" onClick={() => { const api = (window as any).electronAPI; api?.window.setAlwaysOnTop(!onTop); setOnTop(!onTop); }} title={onTop ? '取消置顶' : '窗口置顶'}>{onTop ? '📌' : '📍'}</button>
            <button type="button" className="settings-gear" onClick={() => setGlossaryOpen(true)} title="术语管理">📖</button>
            <button type="button" className="settings-gear" onClick={() => setSettingsOpen(true)} title="设置">⚙</button>
          </div>
        </div>

        <div className="subtitle-area">
          {backendError && (
            <div className="audio-error-banner">
              <span className="audio-error__icon">⚠️</span>
              <span className="audio-error__message">后端错误: {backendError}</span>
              <button type="button" className="audio-error__dismiss" onClick={() => setBackendError(null)}>✕</button>
            </div>
          )}
          {audioError && (
            <div className="audio-error-banner">
              <span className="audio-error__icon">⚠️</span>
              <span className="audio-error__message">{audioError.message}</span>
              <button type="button" className="audio-error__dismiss" onClick={clearError}>✕</button>
            </div>
          )}
          <SubtitleList
            entries={entries}
            placeholder={isTranslating
              ? source === 'system' ? '🔊 正在捕获系统音频...' : '🎤 正在从麦克风录音...'
              : backendPort ? '选择音频源并开始翻译，字幕将实时显示在此区域' : '正在启动后端服务...'}
          />
        </div>

        <div className="control-bar">
          <AudioSourceSelector value={source} onChange={handleSourceChange} disabled={isTranslating} />
          <AudioControls state={audioState} onStart={handleToggle} onStop={handleToggle} />
        </div>
      </main>

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <HistoryPanel open={historyOpen} onClose={() => setHistoryOpen(false)} backendPort={backendPort} />
      <GlossaryManager open={glossaryOpen} onClose={() => setGlossaryOpen(false)} backendPort={backendPort} />
    </div>
  );
}

export default App;
