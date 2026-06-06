/**
 * Settings panel — modal overlay for application configuration.
 *
 * Sections:
 *   - LLM 翻译修正: Provider, API key, model selection
 *   - 界面 (future): Language, subtitle style, etc.
 *
 * Toggled from the status bar gear icon.
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
        {/* Header */}
        <div className="settings-panel__header">
          <h2 className="settings-panel__title">设置</h2>
          <button
            type="button"
            className="settings-panel__close"
            onClick={onClose}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        {/* Content */}
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
            <p className="settings-hint">
              AI 同声传译助手 v0.1.0<br />
              Sherpa-onnx + NMT + LLM<br />
              本地 ASR 引擎，无需联网即可使用基础翻译
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
