import { useState, useCallback, useRef, useEffect } from 'react';
import './App.css';
import { useAudioCapture } from './hooks/useAudioCapture';
import { AudioSourceSelector, AudioControls, AudioVisualizer } from './components/audio';
import { SettingsPanel } from './components/settings';
import { useSettingsStore } from './stores/settingsStore';
import { WebSocketClient } from './services/websocket-client';
import type { AudioSource } from './types/audio';
import type { ConnectionState, ServerMessage } from './types/ws-messages';

const WS_URL = 'ws://127.0.0.1:8000/ws/translate';
const api = (window as { electronAPI?: { window: { minimize: () => void; maximize: () => void; close: () => void } } }).electronAPI;

function App() {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [source, setSource] = useState<AudioSource>('microphone');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [subtitleLines, setSubtitleLines] = useState<Array<{ id: string; original: string; translated: string; isCorrected: boolean }>>([]);

  const wsRef = useRef<WebSocketClient | null>(null);
  const llm = useSettingsStore((s) => s.llm);

  // Initialize WebSocket client once
  if (!wsRef.current) {
    wsRef.current = new WebSocketClient({ url: WS_URL });
    wsRef.current.onStateChange(setConnectionState);
    wsRef.current.onMessage((msg: ServerMessage) => {
      if (msg.type === 'subtitle_draft') {
        setSubtitleLines((prev) => {
          const next = [...prev, {
            id: msg.sequence_id,
            original: msg.original,
            translated: msg.translated,
            isCorrected: false,
          }];
          return next.slice(-20); // Keep last 20 lines
        });
      } else if (msg.type === 'subtitle_corrected') {
        setSubtitleLines((prev) =>
          prev.map((line) =>
            line.id === msg.sequence_id
              ? { ...line, translated: msg.corrected_text, isCorrected: true }
              : line
          )
        );
      }
    });
  }

  const ws = wsRef.current;

  // Audio capture — send chunks via WebSocket
  const {
    state: audioState,
    startCapture,
    stopCapture,
    switchSource,
    error: audioError,
    clearError,
  } = useAudioCapture({
    onChunk: (chunk) => {
      ws.sendAudioChunk(chunk);
    },
  });

  const isTranslating = audioState === 'capturing';

  const handleSourceChange = useCallback((newSource: AudioSource) => {
    setSource(newSource);
    if (isTranslating) switchSource(newSource);
  }, [isTranslating, switchSource]);

  const handleToggleTranslation = useCallback(async () => {
    if (isTranslating) {
      ws.sendControl({ type: 'stop' });
      await stopCapture();
      ws.disconnect();
      setSubtitleLines([]);
    } else {
      ws.connect();
      // Wait briefly for connection, then send start with LLM config
      setTimeout(() => {
        ws.sendControl({
          type: 'start',
          config: {
            source_lang: 'en',
            target_lang: 'zh',
            audio_source: source,
            enable_correction: llm.enabled,
            llm: {
              provider: llm.provider,
              apiKey: llm.apiKey,
              model: llm.model,
              baseUrl: llm.baseUrl,
              enabled: llm.enabled,
            },
          },
        });
        startCapture(source);
      }, 300);
    }
  }, [isTranslating, ws, stopCapture, startCapture, source, llm]);

  return (
    <div className="app-container">
      {/* Title Bar */}
      <header className="title-bar">
        <div className="title-bar__drag-region">
          <span className="title-bar__title">AI 同声传译</span>
        </div>
        <div className="title-bar__controls">
          <button type="button" className="title-bar__btn" onClick={() => api?.window.minimize()} aria-label="最小化">─</button>
          <button type="button" className="title-bar__btn" onClick={() => api?.window.maximize()} aria-label="最大化">□</button>
          <button type="button" className="title-bar__btn title-bar__btn--close" onClick={() => api?.window.close()} aria-label="关闭">✕</button>
        </div>
      </header>

      <main className="main-content">
        {/* Status Bar */}
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

        {/* Subtitle Area */}
        <div className="subtitle-area">
          {audioError && (
            <div className="audio-error-banner">
              <span className="audio-error__icon">⚠️</span>
              <span className="audio-error__message">{audioError.message}</span>
              <button type="button" className="audio-error__dismiss" onClick={clearError}>✕</button>
            </div>
          )}
          {subtitleLines.length > 0 ? (
            <div className="subtitle-list">
              {subtitleLines.map((line) => (
                <div key={line.id} className={`subtitle-line ${line.isCorrected ? 'subtitle-line--corrected' : ''}`}>
                  <div className="subtitle-line__original">{line.original}</div>
                  <div className="subtitle-line__translated">{line.translated}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="subtitle-placeholder">
              <p className="subtitle-hint">
                {isTranslating
                  ? source === 'system' ? '🔊 正在捕获系统音频...' : '🎤 正在从麦克风录音...'
                  : '选择音频源并开始翻译，字幕将实时显示在此区域'}
              </p>
            </div>
          )}
        </div>

        {/* Control Bar */}
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
