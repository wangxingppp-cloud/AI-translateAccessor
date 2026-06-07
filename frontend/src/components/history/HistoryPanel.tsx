/**
 * Translation history panel — browse sessions + search subtitles.
 */
import { useState, useEffect } from 'react';
import { X, Search } from 'lucide-react';

interface SessionInfo {
  id: string;
  name: string;
  source_lang: string;
  target_lang: string;
  asr_provider: string;
  started_at: number;
  ended_at: number | null;
  status: string;
  total_sentences: number;
}

interface SearchResult {
  id: string;
  session_id: string;
  original_text: string;
  translated_text: string;
  is_corrected: boolean;
  created_at: number;
}

/** Subtitle as returned by GET /api/sessions/{id}/subtitles */
interface SubtitleRecord {
  id: string;
  sequence_id: string;
  original_text: string;
  translated_text: string;
  is_corrected: boolean;
  created_at: number;
}

interface HistoryPanelProps {
  open: boolean;
  onClose: () => void;
  backendPort: number | null;
}

export function HistoryPanel({ open, onClose, backendPort }: HistoryPanelProps) {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [sessionSubtitles, setSessionSubtitles] = useState<SubtitleRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const apiBase = backendPort ? `http://127.0.0.1:${backendPort}/api` : '';

  // Load sessions on open
  useEffect(() => {
    if (open && apiBase) {
      console.log('[HISTORY] Loading sessions from', `${apiBase}/sessions`);
      fetch(`${apiBase}/sessions`)
        .then((r) => {
          console.log('[HISTORY] GET /sessions status:', r.status);
          return r.json();
        })
        .then((d) => {
          console.log('[HISTORY] Sessions response:', JSON.stringify(d).slice(0, 500));
          console.log('[HISTORY] Session count:', d.sessions?.length ?? 0);
          setSessions(d.sessions || []);
        })
        .catch((err) => console.error('[HISTORY] GET /sessions error:', err));
    }
  }, [open, apiBase]);

  const loadSession = async (id: string) => {
    setSelectedSession(id);
    setLoading(true);
    console.log('[HISTORY] Loading session subtitles:', id);
    const resp = await fetch(`${apiBase}/sessions/${id}/subtitles`);
    const data = await resp.json();
    console.log('[HISTORY] Subtitles response:', JSON.stringify(data).slice(0, 800));
    console.log('[HISTORY] First subtitle keys:', data.subtitles?.[0] ? Object.keys(data.subtitles[0]) : 'none');
    console.log('[HISTORY] First subtitle raw:', JSON.stringify(data.subtitles?.[0]));
    setSessionSubtitles(data.subtitles || []);
    setLoading(false);
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    const resp = await fetch(`${apiBase}/subtitles/search?q=${encodeURIComponent(searchQuery)}`);
    const data = await resp.json();
    setSearchResults(data.results || []);
    setSelectedSession(null);
    setLoading(false);
  };

  if (!open) return null;

  return (
    <div className="history-overlay" onClick={onClose}>
      <div className="history-panel" onClick={(e) => e.stopPropagation()}>
        <div className="history-panel__header">
          <h2 className="history-panel__title">翻译历史</h2>
          <button type="button" className="history-panel__close" onClick={onClose} aria-label="关闭">
            <X size={16} strokeWidth={2} />
          </button>
        </div>

        {/* Search */}
        <div className="history-search">
          <input
            type="text" className="settings-input"
            value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="搜索原文或译文..."
          />
          <button type="button" className="test-btn" onClick={handleSearch}>
            <Search size={14} strokeWidth={2} />
            搜索
          </button>
        </div>

        <div className="history-panel__body">
          {loading && <p className="history-loading">加载中...</p>}

          {/* Search results */}
          {searchResults.length > 0 && (
            <div className="history-section">
              <h3 className="history-section__title">搜索结果 ({searchResults.length})</h3>
              {searchResults.map((r) => (
                <div key={r.id} className="history-item">
                  <div className="history-item__original">{r.original_text}</div>
                  <div className="history-item__translated">{r.translated_text || '(未翻译)'}</div>
                  <div className="history-item__meta">
                    {new Date(r.created_at * 1000).toLocaleTimeString()}
                    {r.is_corrected && ' · LLM 修正'}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Session list */}
          {searchResults.length === 0 && !selectedSession && (
            <div className="history-section">
              <h3 className="history-section__title">最近会话</h3>
              {sessions.length === 0 && <p className="history-hint">暂无历史记录</p>}
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className="history-item history-item--session"
                  onClick={() => loadSession(s.id)}
                >
                  {s.name && <div className="history-item__name">{s.name}</div>}
                  <div className="history-item__meta">
                    {new Date(s.started_at * 1000).toLocaleString()}
                    {' · '}{s.source_lang.toUpperCase()} → {s.target_lang.toUpperCase()}
                    {' · '}{s.total_sentences} 句
                    {s.status === 'active' && ' · 进行中'}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Session detail */}
          {selectedSession && sessionSubtitles.length > 0 && (
            <div className="history-section">
              <div className="history-section__header">
                <h3 className="history-section__title">会话字幕</h3>
                <button type="button" className="history-back" onClick={() => { setSelectedSession(null); setSessionSubtitles([]); }}>← 返回</button>
              </div>
              {sessionSubtitles.map((sub) => (
                <div key={sub.id} className="history-item">
                  <div className="history-item__original">{sub.original_text}</div>
                  <div className="history-item__translated">{sub.translated_text || '(未翻译)'}</div>
                  <div className="history-item__meta">
                    {sub.created_at ? new Date(sub.created_at * 1000).toLocaleTimeString() : ''}
                    {sub.is_corrected && ' · LLM 修正'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
