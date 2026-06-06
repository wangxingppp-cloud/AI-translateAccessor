/**
 * Settings panel — modal overlay for application configuration.
 */
import { ModelSettings } from './ModelSettings';

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  if (!open) return null;

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="settings-panel__header">
          <h2 className="settings-panel__title">设置</h2>
          <button type="button" className="settings-panel__close" onClick={onClose} aria-label="关闭">✕</button>
        </div>
        <div className="settings-panel__body">
          <ModelSettings />
          <div className="settings-section">
            <h3 className="settings-section__title">语言</h3>
            <div className="settings-row">
              <label className="settings-label">源语言 → 目标语言</label>
              <div className="lang-pair">
                <span className="lang-badge">English</span>
                <span className="lang-arrow">→</span>
                <span className="lang-badge">中文</span>
              </div>
            </div>
            <p className="settings-hint">更多语言支持将在后续版本中添加。</p>
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
