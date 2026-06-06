import { useState, useCallback } from 'react';
import './App.css';
import type { ElectronAPI } from './types/electron';
import { useAudioCapture } from './hooks/useAudioCapture';
import { AudioSourceSelector, AudioControls, AudioVisualizer } from './components/audio';
import { SettingsPanel } from './components/settings';
import type { AudioSource } from './types/audio';
import type { ConnectionState } from './types/ws-messages';

const api = (window as Window & { electronAPI?: ElectronAPI }).electronAPI;

function App() {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [source, setSource] = useState<AudioSource>('microphone');
  const [settingsOpen, setSettingsOpen] = useState(false);

  const {
    state: audioState,
    startCapture,
    stopCapture,
    switchSource,
    error: audioError,
    clearError,
  } = useAudioCapture({
    onChunk: (_chunk) => {
      // Will be wired to WebSocket in next integration phase
    },
  });

  const isTranslating = audioState === 'capturing';

  const handleSourceChange = useCallback((newSource: AudioSource) => {
    setSource(newSource);
    if (isTranslating) {
      switchSource(newSource);
    }
  }, [isTranslating, switchSource]);

  const handleToggleTranslation = useCallback(() => {
    if (isTranslating) {
      stopCapture();
    } else {
      startCapture(source);
    }
  }, [isTranslating, stopCapture, startCapture, source]);

  return (
    <div className="app-container">
      {/* Custom Title Bar */}
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

      {/* Main Content */}
      <main className="main-content">
        {/* Status Bar */}
        <div className="status-bar">
          <span className={`status-indicator ${connectionState === 'connected' ? 'status-indicator--connected' : 'status-indicator--disconnected'}`}>
            {connectionState === 'connected' ? '🟢 已连接' : '⚫ 未连接'}
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
          <div className="subtitle-placeholder">
            <p className="subtitle-hint">
              {isTranslating
                ? source === 'system'
                  ? '🔊 正在捕获系统音频...'
                  : '🎤 正在从麦克风录音...'
                : '选择音频源并开始翻译，字幕将实时显示在此区域'}
            </p>
          </div>
        </div>

        {/* Control Bar */}
        <div className="control-bar">
          <AudioSourceSelector
            value={source}
            onChange={handleSourceChange}
            disabled={isTranslating}
          />
          <AudioControls
            state={audioState}
            onStart={handleToggleTranslation}
            onStop={handleToggleTranslation}
          />
        </div>
      </main>

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

export default App;
