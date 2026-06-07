/**
 * ASR provider configuration with local draft + Apply button.
 */
import { useState } from 'react';
import { useSettingsStore } from '../../stores/settingsStore';
import { ASR_PROVIDERS, type AsrProvider, type AsrConfig } from '../../types/config';

export function AsrSettings() {
  const storedAsr = useSettingsStore((s) => s.asr);
  const setAsrProvider = useSettingsStore((s) => s.setAsrProvider);
  const setAsrApiKey = useSettingsStore((s) => s.setAsrApiKey);
  const setAsrApiSecret = useSettingsStore((s) => s.setAsrApiSecret);
  const setAsrAppId = useSettingsStore((s) => s.setAsrAppId);
  const setAsrBaseUrl = useSettingsStore((s) => s.setAsrBaseUrl);

  // Local draft — only saved on Apply
  const [draft, setDraft] = useState<AsrConfig>({ ...storedAsr });
  const [saved, setSaved] = useState(false);

  const providerInfo = ASR_PROVIDERS.find((p) => p.id === draft.provider);
  const isCloud = draft.provider !== 'local';
  const isValid = !isCloud || (
    draft.apiKey?.trim() &&
    draft.apiSecret?.trim() &&
    (draft.provider !== 'iflytek' || draft.appId?.trim())
  );

  const handleApply = () => {
    setAsrProvider(draft.provider);
    setAsrApiKey(draft.apiKey);
    setAsrApiSecret(draft.apiSecret);
    setAsrAppId(draft.appId);
    setAsrBaseUrl(draft.baseUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="settings-section">
      <h3 className="settings-section__title">语音识别引擎</h3>
      <p className="settings-section__desc">本地离线免费延迟较高，云端 API 低延迟按量付费。</p>

      <div className="settings-row">
        <label className="settings-label">选择引擎</label>
        <div className="provider-grid">
          {ASR_PROVIDERS.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`provider-card ${draft.provider === p.id ? 'provider-card--active' : ''} ${p.id === 'baidu' ? 'provider-card--disabled' : ''}`}
              onClick={() => p.id !== 'baidu' && setDraft((d) => ({ ...d, provider: p.id, baseUrl: p.defaultBaseUrl }))}
              disabled={p.id === 'baidu'}
            >
              <span className="provider-card__name">{p.name}</span>
              <span className="provider-card__desc">{p.description}</span>
              <span className="provider-card__meta">{p.latency} &middot; {p.cost}</span>
              {p.id === storedAsr.provider && <span className="provider-card__badge">使用中</span>}
              {p.id === 'baidu' && <span className="provider-card__badge provider-card__badge--dev">开发中</span>}
            </button>
          ))}
        </div>
      </div>

      {isCloud && (
        <div className="settings-body">
          {draft.provider === 'iflytek' && (
            <div className="settings-row">
              <label className="settings-label" htmlFor="asr-app-id">APPID</label>
              <input id="asr-app-id" type="text" className="settings-input"
                value={draft.appId} onChange={(e) => setDraft((d) => ({ ...d, appId: e.target.value }))}
                placeholder="讯飞 APPID" />
            </div>
          )}
          <div className="settings-row">
            <label className="settings-label" htmlFor="asr-api-key">API Key</label>
            <input id="asr-api-key" type="password" className="settings-input"
              value={draft.apiKey} onChange={(e) => setDraft((d) => ({ ...d, apiKey: e.target.value }))}
              placeholder={draft.provider === 'iflytek' ? '讯飞 API Key' : '百度 API Key'} />
          </div>
          <div className="settings-row">
            <label className="settings-label" htmlFor="asr-api-secret">API Secret</label>
            <input id="asr-api-secret" type="password" className="settings-input"
              value={draft.apiSecret} onChange={(e) => setDraft((d) => ({ ...d, apiSecret: e.target.value }))}
              placeholder={draft.provider === 'iflytek' ? '讯飞 API Secret' : '百度 Secret Key'} />
          </div>
          <div className="settings-row">
            <label className="settings-label" htmlFor="asr-base-url">API 地址</label>
            <input id="asr-base-url" type="text" className="settings-input"
              value={draft.baseUrl} onChange={(e) => setDraft((d) => ({ ...d, baseUrl: e.target.value }))}
              placeholder={providerInfo?.defaultBaseUrl} />
          </div>
        </div>
      )}

      {!isCloud && <p className="settings-hint">使用本地 SenseVoice 多语种模型（228MB）。无需网络，延迟 ~2s。</p>}

      <div className="settings-row">
        <button type="button" className="control-btn control-btn--start" onClick={handleApply}
          disabled={!isValid} title={!isValid ? '云端引擎需要填写所有必填字段（讯飞需要 APPID + API Key + API Secret）' : '应用设置'}>
          {saved ? '✓ 已应用' : '应用'}
        </button>
      </div>
    </div>
  );
}
