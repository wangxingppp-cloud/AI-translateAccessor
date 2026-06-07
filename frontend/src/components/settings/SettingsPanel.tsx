/**
 * Settings panel — tabbed layout (ASR + LLM) with Apply/Cancel.
 */
import { useState } from 'react';
import { X } from 'lucide-react';
import { AsrSettings } from './AsrSettings';
import { ModelSettings } from './ModelSettings';
import { TtsSettings } from './TtsSettings';
import { useSettingsStore } from '../../stores/settingsStore';
import { SOURCE_LANGS, TARGET_LANGS } from '../../types/config';

type Tab = 'asr' | 'llm' | 'tts';

function LangSelector() {
  const sourceLang = useSettingsStore((s) => s.sourceLang);
  const targetLang = useSettingsStore((s) => s.targetLang);
  const setSourceLang = useSettingsStore((s) => s.setSourceLang);
  const setTargetLang = useSettingsStore((s) => s.setTargetLang);

  return (
    <div className="settings-row">
      <div className="lang-select-row">
        <select className="settings-select" value={sourceLang} onChange={(e) => setSourceLang(e.target.value)} title="源语言">
          {SOURCE_LANGS.map((l) => <option key={l.code} value={l.code}>{l.label} ({l.name})</option>)}
        </select>
        <span className="lang-arrow">→</span>
        <select className="settings-select" value={targetLang} onChange={(e) => setTargetLang(e.target.value)} title="目标语言">
          {TARGET_LANGS.map((l) => <option key={l.code} value={l.code}>{l.label} ({l.name})</option>)}
        </select>
      </div>
    </div>
  );
}

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const [tab, setTab] = useState<Tab>('asr');

  if (!open) return null;

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="settings-panel__header">
          <div className="settings-tabs">
            <button type="button" className={`settings-tab ${tab === 'asr' ? 'settings-tab--active' : ''}`} onClick={() => setTab('asr')}>语音识别 (ASR)</button>
            <button type="button" className={`settings-tab ${tab === 'llm' ? 'settings-tab--active' : ''}`} onClick={() => setTab('llm')}>LLM 翻译修正</button>
            <button type="button" className={`settings-tab ${tab === 'tts' ? 'settings-tab--active' : ''}`} onClick={() => setTab('tts')}>语音合成 (TTS)</button>
          </div>
          <button type="button" className="settings-panel__close" onClick={onClose} aria-label="关闭">
            <X size={16} strokeWidth={2} />
          </button>
        </div>

        <div className="settings-panel__body">
          {tab === 'asr' && <AsrSettings />}
          {tab === 'llm' && <ModelSettings />}
          {tab === 'tts' && <TtsSettings />}
        </div>

        <div className="settings-panel__footer">
          <div className="settings-section">
            <h3 className="settings-section__title">翻译语言</h3>
            <p className="settings-section__desc">源语言（视频中的语言）→ 目标语言（字幕显示的语言）</p>
            <LangSelector />
          </div>
          <div className="settings-section">
            <h3 className="settings-section__title">关于</h3>
            <p className="settings-hint">AI 同声传译助手 v0.1.0 / Sherpa-onnx + LLM</p>
          </div>
        </div>
      </div>
    </div>
  );
}
