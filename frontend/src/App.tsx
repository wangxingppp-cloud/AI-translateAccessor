import { useState, useCallback, useRef, useEffect } from 'react';
import { Settings, Clock, BookOpen, Pin, PinOff, AlertTriangle } from 'lucide-react';
import './App.css';
import { useAudioCapture } from './hooks/useAudioCapture';
import { AudioSourceSelector, AudioControls, AudioVisualizer, SaveDialog } from './components/audio';
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
  const [isPaused, setIsPaused] = useState(false);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);

  const wsRef = useRef<WebSocketClient | null>(null);
  const llm = useSettingsStore((s) => s.llm);
  const asr = useSettingsStore((s) => s.asr);
  const srcLang = useSettingsStore((s) => s.sourceLang);
  const tgtLang = useSettingsStore((s) => s.targetLang);
  const { wsState, backendPort, backendError, setWsState, setBackendPort, setBackendError } = useConnectionStore();
  const { entries, pending, addEntry, correctEntry, clear: clearSubtitles } = useSubtitleStore();

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
      if (msg.type === 'subtitle_draft') {
        console.log(`[DBG-TRACK] ⑦前端收到字幕: original='${(msg as any).original?.slice(0, 40)}' translated='${(msg as any).translated?.slice(0, 40)}' is_sentence_end=${(msg as any).is_sentence_end}`);
      }
      console.log('[WS-IN]', msg.type, msg.type === 'subtitle_draft' ? (msg as any).original?.slice(0, 30) : '');
      if (msg.type === 'subtitle_draft') {
        if (msg.is_sentence_end && msg.translated) {
          // Translation update for committed entry
          useSubtitleStore.getState().updateTranslation(msg.sequence_id, msg.translated);
        } else {
          const entry = { id: msg.sequence_id, original: msg.original, translated: msg.translated, isCorrected: false, isFinal: msg.is_sentence_end, timestamp: msg.timestamp };
          addEntry(entry);
        }
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
  const chunkCount = useRef(0);
  const sendCount = useRef(0);
  const { state: audioState, startCapture, stopCapture, switchSource, error: audioError, clearError } = useAudioCapture({
    onChunk: (chunk) => {
      chunkCount.current++;
      if (chunkCount.current <= 5 || chunkCount.current % 50 === 0) {
        console.log(`[DBG-TRACK] ①前端采集 chunk #${chunkCount.current}: ${chunk.byteLength}B`);
      }
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
        sendCount.current++;
        if (sendCount.current <= 5 || sendCount.current % 20 === 0) {
          console.log(`[DBG-TRACK] ②前端发送 WS #${sendCount.current}: ${merged.byteLength}B, wsState=${wsRef.current ? 'exists' : 'null'}`);
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

  const handleStart = useCallback(() => {
    const client = wsRef.current; if (!client) return;
    client.sendControl({
      type: 'start',
      config: {
        source_lang: srcLang, target_lang: tgtLang, audio_source: source,
        enable_correction: llm.enabled,
        llm: { provider: llm.provider, apiKey: llm.apiKey, model: llm.model, baseUrl: llm.baseUrl, enabled: llm.enabled },
        asr: { provider: asr.provider, apiKey: asr.apiKey, apiSecret: asr.apiSecret, appId: asr.appId, baseUrl: asr.baseUrl },
      },
    });
    startCapture(source);
    setIsPaused(false);
  }, [startCapture, source, llm, asr]);

  const handlePause = useCallback(() => {
    wsRef.current?.sendControl({ type: 'pause' });
    setIsPaused(true);
  }, []);

  const handleResume = useCallback(() => {
    wsRef.current?.sendControl({ type: 'resume' });
    setIsPaused(false);
  }, []);

  const handleStopRequest = useCallback(() => {
    // Pause audio capture but don't clear yet — show save dialog first
    wsRef.current?.sendControl({ type: 'pause' });
    setIsPaused(true);
    setSaveDialogOpen(true);
  }, []);

  const handleSave = useCallback(async (name: string) => {
    const client = wsRef.current;
    console.log('[SAVE] handleSave called', { name, backendPort, entryCount: entries.length, srcLang, tgtLang });

    // Persist current subtitles to history via REST API
    if (backendPort && entries.length > 0) {
      const payload = {
        name,
        source_lang: srcLang,
        target_lang: tgtLang,
        subtitles: entries.map((e) => ({
          original: e.original,
          translated: e.translated,
          timestamp: e.timestamp,
        })),
      };
      console.log('[SAVE] POST payload:', JSON.stringify(payload).slice(0, 500));

      try {
        const url = `http://127.0.0.1:${backendPort}/api/sessions`;
        console.log('[SAVE] POST →', url);
        const resp = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        console.log('[SAVE] POST response status:', resp.status, resp.statusText);
        const respBody = await resp.text();
        console.log('[SAVE] POST response body:', respBody);
        if (!resp.ok) console.warn('[SAVE] POST failed:', resp.status, respBody);
        else console.log('[SAVE] POST success:', respBody);
      } catch (err) {
        console.error('[SAVE] POST error:', err);
      }
    } else {
      console.warn('[SAVE] Skipped POST:', { backendPort, entryCount: entries.length });
    }
    client?.sendControl({ type: 'stop' });
    await stopCapture();
    clearSubtitles();
    setIsPaused(false);
    setSaveDialogOpen(false);
  }, [backendPort, entries, srcLang, tgtLang, stopCapture, clearSubtitles]);

  const handleDiscard = useCallback(async () => {
    wsRef.current?.sendControl({ type: 'stop' });
    await stopCapture();
    clearSubtitles();
    setIsPaused(false);
    setSaveDialogOpen(false);
  }, [stopCapture, clearSubtitles]);

  const handleSaveCancel = useCallback(() => {
    // User cancelled — resume translation
    wsRef.current?.sendControl({ type: 'resume' });
    setIsPaused(false);
    setSaveDialogOpen(false);
  }, []);

  const connected = wsState === 'connected';
  const connecting = wsState === 'connecting' || wsState === 'reconnecting';

  return (
    <div className="app-container">
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
        <div className="status-bar">
          <span className={`status-indicator ${connected ? 'status-indicator--connected' : 'status-indicator--disconnected'}`}>
            <span className="status-dot" />
            {connected ? '已连接' : connecting ? '连接中...' : '未连接'}
          </span>
          <div className="status-bar__right">
            <AudioVisualizer state={audioState} />
            <span className="status-lang">{srcLang.toUpperCase()} → {tgtLang.toUpperCase()}</span>
            <button type="button" className="toolbar-btn" onClick={() => setHistoryOpen(true)} title="翻译历史" aria-label="翻译历史">
              <Clock size={15} strokeWidth={1.8} />
            </button>
            <button
              type="button"
              className={`toolbar-btn ${onTop ? 'toolbar-btn--active' : ''}`}
              onClick={() => { const api = (window as any).electronAPI; api?.window.setAlwaysOnTop(!onTop); setOnTop(!onTop); }}
              title={onTop ? '取消置顶' : '窗口置顶'}
              aria-label={onTop ? '取消置顶' : '窗口置顶'}
            >
              {onTop ? <Pin size={15} strokeWidth={1.8} /> : <PinOff size={15} strokeWidth={1.8} />}
            </button>
            <button type="button" className="toolbar-btn" onClick={() => setGlossaryOpen(true)} title="术语管理" aria-label="术语管理">
              <BookOpen size={15} strokeWidth={1.8} />
            </button>
            <button type="button" className="toolbar-btn" onClick={() => setSettingsOpen(true)} title="设置" aria-label="设置">
              <Settings size={15} strokeWidth={1.8} />
            </button>
          </div>
        </div>

        <div className="subtitle-area">
          {backendError && (
            <div className="audio-error-banner">
              <span className="audio-error__icon"><AlertTriangle size={15} /></span>
              <span className="audio-error__message">后端错误: {backendError}</span>
              <button type="button" className="audio-error__dismiss" onClick={() => setBackendError(null)}>✕</button>
            </div>
          )}
          {audioError && (
            <div className="audio-error-banner">
              <span className="audio-error__icon"><AlertTriangle size={15} /></span>
              <span className="audio-error__message">{audioError.message}</span>
              <button type="button" className="audio-error__dismiss" onClick={clearError}>✕</button>
            </div>
          )}
          <SubtitleList
            entries={entries}
            current={pending}
            placeholder={isTranslating
              ? source === 'system' ? '正在捕获系统音频...' : '正在从麦克风录音...'
              : backendPort ? '选择音频源并开始翻译，字幕将实时显示在此区域' : '正在启动后端服务...'}
          />
        </div>

        <div className="control-bar">
          <AudioSourceSelector value={source} onChange={handleSourceChange} disabled={isTranslating} />
          <AudioControls
            state={audioState}
            isPaused={isPaused}
            onStart={handleStart}
            onPause={handlePause}
            onResume={handleResume}
            onStopRequest={handleStopRequest}
          />
        </div>
      </main>

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <HistoryPanel open={historyOpen} onClose={() => setHistoryOpen(false)} backendPort={backendPort} />
      <GlossaryManager open={glossaryOpen} onClose={() => setGlossaryOpen(false)} backendPort={backendPort} />
      <SaveDialog
        open={saveDialogOpen}
        onSave={handleSave}
        onDiscard={handleDiscard}
        onCancel={handleSaveCancel}
      />
    </div>
  );
}

export default App;
