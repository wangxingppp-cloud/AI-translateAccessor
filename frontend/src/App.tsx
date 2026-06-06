import { useState, useCallback, useRef, useEffect } from 'react';
import './App.css';
import { useAudioCapture } from './hooks/useAudioCapture';
import { AudioSourceSelector, AudioControls, AudioVisualizer } from './components/audio';
import { SettingsPanel } from './components/settings';
import { SubtitleList, type SubtitleEntry } from './components/subtitle';
import { useSettingsStore } from './stores/settingsStore';
import { WebSocketClient } from './services/websocket-client';
import type { AudioSource } from './types/audio';
import type { ConnectionState, ServerMessage } from './types/ws-messages';

const DEFAULT_WS_PORT = 8000;
const win = window as { electronAPI?: { window: { minimize: () => void; maximize: () => void; close: () => void }; backend?: { onReady: (cb: (p: number) => void) => void; onError: (cb: (m: string) => void) => void } } };
const api = win.electronAPI;

function App() {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [wsPort, setWsPort] = useState<number | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [source, setSource] = useState<AudioSource>('microphone');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [subtitleLines, setSubtitleLines] = useState<SubtitleEntry[]>([]);

  const wsRef = useRef<WebSocketClient | null>(null);
  const llm = useSettingsStore((s) => s.llm);

  // Discover backend port from Electron (already started or soon)
  useEffect(() => {
    if (api?.backend) {
      // Check if backend is already ready (port available before mount)
      api.backend.getPort().then((port: number | null) => {
        if (port) setWsPort(port);
      });
      // Listen for future readiness events
      api.backend.onReady((port: number) => setWsPort(port));
      api.backend.onError((msg: string) => setBackendError(msg));
    }
    if (!api) setWsPort(DEFAULT_WS_PORT); // No Electron = dev mode
  }, []);

  // Create WebSocket client when port is known
  useEffect(() => {
    if (!wsPort) return;
    const url = `ws://127.0.0.1:${wsPort}/ws/translate`;
    const ws = new WebSocketClient({ url });
    ws.onStateChange(setConnectionState);
    ws.onMessage((msg: ServerMessage) => {
      if (msg.type === 'subtitle_draft') {
        setSubtitleLines((prev) => {
          const next = [...prev, {
            id: msg.sequence_id, original: msg.original, translated: msg.translated, isCorrected: false,
          }];
          return next.slice(-20);
        });
      } else if (msg.type === 'subtitle_corrected') {
        setSubtitleLines((prev) =>
          prev.map((line) =>
            line.id === msg.sequence_id
              ? { ...line, translated: msg.corrected_text, isCorrected: true, diff: msg.diff }
              : line
          )
        );
      }
    });
    wsRef.current = ws;
    return () => { ws.disconnect(); };
  }, [wsPort]);

  const ws = wsRef.current;

  // Audio capture — send chunks via WebSocket
  const {
    state: audioState, startCapture, stopCapture, switchSource, error: audioError, clearError,
  } = useAudioCapture({
    onChunk: (chunk) => { ws?.sendAudioChunk(chunk); },
  });

  const isTranslating = audioState === 'capturing';

  const handleSourceChange = useCallback((newSource: AudioSource) => {
    setSource(newSource);
    if (isTranslating) switchSource(newSource);
  }, [isTranslating, switchSource]);

  const handleToggleTranslation = useCallback(async () => {
    const client = wsRef.current;
    if (!client) return;

    if (isTranslating) {
      client.sendControl({ type: 'stop' });
      await stopCapture();
      client.disconnect();
      setSubtitleLines([]);
    } else {
      client.connect();
      setTimeout(() => {
        if (!wsRef.current) return;
        wsRef.current.sendControl({
          type: 'start',
          config: {
            source_lang: 'en', target_lang: 'zh', audio_source: source,
            enable_correction: llm.enabled,
            llm: { provider: llm.provider, apiKey: llm.apiKey, model: llm.model, baseUrl: llm.baseUrl, enabled: llm.enabled },
          },
        });
        startCapture(source);
      }, 500);
    }
  }, [isTranslating, stopCapture, startCapture, source, llm]);

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
          <span className={`status-indicator ${connectionState === 'connected' ? 'status-indicator--connected' : 'status-indicator--disconnected'}`}>
            {connectionState === 'connected' ? '🟢 已连接' : connectionState === 'connecting' || connectionState === 'reconnecting' ? '🟡 连接中...' : '⚫ 未连接'}
          </span>
          <div className="status-bar__right">
            <AudioVisualizer state={audioState} />
            <span className="status-lang">English → 中文</span>
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
            entries={subtitleLines}
            placeholder={isTranslating
              ? source === 'system' ? '🔊 正在捕获系统音频...' : '🎤 正在从麦克风录音...'
              : wsPort ? '选择音频源并开始翻译，字幕将实时显示在此区域' : '正在启动后端服务...'}
          />
        </div>

        <div className="control-bar">
          <AudioSourceSelector value={source} onChange={handleSourceChange} disabled={isTranslating} />
          <AudioControls state={audioState} onStart={handleToggleTranslation} onStop={handleToggleTranslation} />
        </div>
      </main>

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

export default App;
