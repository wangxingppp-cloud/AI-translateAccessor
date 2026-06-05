import { useState } from 'react';
import './App.css';
import type { ElectronAPI } from './types/electron';

const api = (window as Window & { electronAPI?: ElectronAPI }).electronAPI;

function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);

  return (
    <div className="app-container">
      {/* Custom Title Bar */}
      <header className="title-bar">
        <div className="title-bar__drag-region">
          <span className="title-bar__title">AI 同声传译</span>
        </div>
        <div className="title-bar__controls">
          <button
            type="button"
            className="title-bar__btn"
            onClick={() => api?.window.minimize()}
            aria-label="最小化"
          >
            ─
          </button>
          <button
            type="button"
            className="title-bar__btn"
            onClick={() => api?.window.maximize()}
            aria-label="最大化"
          >
            □
          </button>
          <button
            type="button"
            className="title-bar__btn title-bar__btn--close"
            onClick={() => api?.window.close()}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {/* Status Bar */}
        <div className="status-bar">
          <span className={`status-indicator ${isConnected ? 'status-indicator--connected' : 'status-indicator--disconnected'}`}>
            {isConnected ? '🟢 已连接' : '⚫ 未连接'}
          </span>
          <span className="status-lang">English → 中文</span>
        </div>

        {/* Subtitle Area */}
        <div className="subtitle-area">
          <div className="subtitle-placeholder">
            <p className="subtitle-hint">
              选择音频源并开始翻译，字幕将实时显示在此区域
            </p>
          </div>
        </div>

        {/* Control Bar */}
        <div className="control-bar">
          <div className="control-bar__source">
            <label className="control-label">音频源</label>
            <select className="control-select" defaultValue="microphone" title="选择音频输入源">
              <option value="microphone">🎤 麦克风</option>
              <option value="system">🔊 系统音频</option>
            </select>
          </div>

          <button
            type="button"
            className={`control-btn ${isTranslating ? 'control-btn--stop' : 'control-btn--start'}`}
            onClick={() => setIsTranslating(!isTranslating)}
          >
            {isTranslating ? '⏹ 停止' : '▶ 开始翻译'}
          </button>
        </div>
      </main>
    </div>
  );
}

export default App;
