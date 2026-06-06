/**
 * Settings panel — tabbed layout (ASR + LLM) with Apply/Cancel.
 */
import { useState } from 'react';
import { AsrSettings } from './AsrSettings';
import { ModelSettings } from './ModelSettings';

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

type Tab = 'asr' | 'llm';

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const [tab, setTab] = useState<Tab>('asr');

  if (!open) return null;

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="settings-panel__header">
          <div className="settings-tabs">
            <button
              type="button"
              className={`settings-tab ${tab === 'asr' ? 'settings-tab--active' : ''}`}
              onClick={() => setTab('asr')}
            >
              语音识别 (ASR)
            </button>
            <button
              type="button"
              className={`settings-tab ${tab === 'llm' ? 'settings-tab--active' : ''}`}
              onClick={() => setTab('llm')}
            >
              LLM 翻译修正
            </button>
          </div>
          <button type="button" className="settings-panel__close" onClick={onClose} aria-label="关闭">✕</button>
        </div>

        <div className="settings-panel__body">
          {tab === 'asr' ? <AsrSettings /> : <ModelSettings />}
        </div>

        <div className="settings-panel__footer">
          <div className="settings-section">
            <h3 className="settings-section__title">语言</h3>
            <div className="lang-pair">
              <span className="lang-badge">English</span>
              <span className="lang-arrow">→</span>
              <span className="lang-badge">中文</span>
            </div>
          </div>
          <div className="settings-section">
            <h3 className="settings-section__title">关于</h3>
            <p className="settings-hint">AI 同声传译助手 v0.1.0 / Sherpa-onnx + NMT + LLM</p>
          </div>
        </div>
      </div>
    </div>
  );
}
