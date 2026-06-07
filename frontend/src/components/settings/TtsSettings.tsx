/**
 * TTS provider configuration with local draft + Apply button.
 *
 * Supports: local (ZipVoice), edge (Edge TTS), openai, custom.
 */
import { useState } from 'react';
import { useSettingsStore } from '../../stores/settingsStore';
import { TTS_PROVIDERS, type TtsConfig } from '../../types/config';

type TestStatus = 'idle' | 'testing' | 'success' | 'error';

export function TtsSettings() {
  const storedTts = useSettingsStore((s) => s.tts);
  const setTtsConfig = useSettingsStore((s) => s.setTtsConfig);

  const [draft, setDraft] = useState<TtsConfig>({ ...storedTts });
  const [saved, setSaved] = useState(false);
  const [testStatus, setTestStatus] = useState<TestStatus>('idle');
  const [testMessage, setTestMessage] = useState('');

  const providerInfo = TTS_PROVIDERS.find((p) => p.id === draft.provider);
  const isCloud = draft.provider !== 'local';
  const hasVoices = (providerInfo?.voices.length ?? 0) > 0;
  const isValid = !draft.enabled || !isCloud || !providerInfo?.needsApiKey || draft.apiKey.trim();

  const handleApply = () => {
    setTtsConfig(draft);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleTest = async () => {
    setTestStatus('testing');
    setTestMessage('');
    try {
      // Test by synthesizing a short phrase
      const base = draft.baseUrl.replace(/\/+$/, '') || 'https://api.openai.com/v1';
      const resp = await fetch(`${base}/audio/speech`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${draft.apiKey}`,
        },
        body: JSON.stringify({
          model: draft.model || 'tts-1',
          voice: draft.voice || 'alloy',
          input: '你好',
        }),
        signal: AbortSignal.timeout(15000),
      });
      if (resp.ok) {
        setTestStatus('success');
        setTestMessage(`连接成功 — 模型 "${draft.model}" 音色 "${draft.voice}" 可用`);
      } else {
        const err = await resp.text().catch(() => '');
        if (resp.status === 401 || resp.status === 403) setTestMessage('API Key 无效');
        else setTestMessage(`请求失败 (${resp.status}): ${err.slice(0, 100)}`);
        setTestStatus('error');
      }
    } catch (e: unknown) {
      const msg = (e as Error).message || '';
      if (msg.includes('timeout') || msg.includes('AbortError')) setTestMessage('连接超时');
      else if (msg.includes('Failed to fetch')) setTestMessage('无法连接到服务器');
      else setTestMessage(msg);
      setTestStatus('error');
    }
  };

  return (
    <div className="settings-section">
      <h3 className="settings-section__title">语音合成引擎</h3>
      <p className="settings-section__desc">点击译文旁的小喇叭即可朗读。本地离线免费，云端效果更好。</p>

      <div className="settings-row">
        <label className="settings-label">启用 TTS</label>
        <button type="button" className={`toggle ${draft.enabled ? 'toggle--on' : ''}`}
          onClick={() => setDraft((d) => ({ ...d, enabled: !d.enabled }))}
          role="switch" aria-checked={draft.enabled}>
          <span className="toggle__knob" />
        </button>
      </div>
      {!draft.enabled && <p className="settings-hint">TTS 已关闭，小喇叭图标不会显示。</p>}

      <div className={`settings-body ${!draft.enabled ? 'settings-body--disabled' : ''}`}>
        <div className="settings-row">
          <label className="settings-label">选择引擎</label>
          <div className="provider-grid">
            {TTS_PROVIDERS.map((p) => (
              <button key={p.id} type="button"
                className={`provider-card ${draft.provider === p.id ? 'provider-card--active' : ''} ${p.id === 'custom' ? 'provider-card--disabled' : ''}`}
                onClick={() => p.id !== 'custom' && setDraft((d) => ({
                  ...d, provider: p.id, voice: p.defaultVoice, baseUrl: p.defaultBaseUrl,
                }))}
                disabled={p.id === 'custom'}>
                <span className="provider-card__name">{p.name}</span>
                <span className="provider-card__desc">{p.description}</span>
                <span className="provider-card__meta">{p.latency} &middot; {p.cost}</span>
                {p.id === storedTts.provider && <span className="provider-card__badge">使用中</span>}
                {p.id === 'custom' && <span className="provider-card__badge provider-card__badge--dev">开发中</span>}
              </button>
            ))}
          </div>
        </div>

        {isCloud && (
          <>
            {hasVoices && (
              <div className="settings-row">
                <label className="settings-label">音色</label>
                <select className="settings-select" value={draft.voice}
                  onChange={(e) => setDraft((d) => ({ ...d, voice: e.target.value }))}>
                  {providerInfo!.voices.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </div>
            )}

            {providerInfo?.needsApiKey && (
              <>
                <div className="settings-row">
                  <label className="settings-label" htmlFor="tts-api-key">API Key</label>
                  <input id="tts-api-key" type="password" className="settings-input"
                    value={draft.apiKey} onChange={(e) => setDraft((d) => ({ ...d, apiKey: e.target.value }))}
                    placeholder="输入 API Key" />
                </div>

                {draft.provider === 'openai' && (
                  <div className="settings-row">
                    <label className="settings-label" htmlFor="tts-model">模型</label>
                    <select id="tts-model" className="settings-select" value={draft.model}
                      onChange={(e) => setDraft((d) => ({ ...d, model: e.target.value }))}>
                      <option value="tts-1">tts-1（快速）</option>
                      <option value="tts-1-hd">tts-1-hd（高质量）</option>
                    </select>
                  </div>
                )}

                {draft.provider === 'custom' && (
                  <div className="settings-row">
                    <label className="settings-label" htmlFor="tts-base-url">API 地址</label>
                    <input id="tts-base-url" type="text" className="settings-input"
                      value={draft.baseUrl} onChange={(e) => setDraft((d) => ({ ...d, baseUrl: e.target.value }))}
                      placeholder="https://api.example.com/v1" />
                  </div>
                )}

                <div className="settings-row">
                  <div className="test-row">
                    <button type="button" className="test-btn" onClick={handleTest} disabled={testStatus === 'testing' || !draft.apiKey.trim()}>
                      {testStatus === 'testing' ? '⏳ 测试中...' : '🔍 测试连接'}
                    </button>
                    {testStatus === 'success' && <span className="test-msg test-msg--ok">{testMessage}</span>}
                    {testStatus === 'error' && <span className="test-msg test-msg--err">{testMessage}</span>}
                  </div>
                </div>
              </>
            )}

            {!providerInfo?.needsApiKey && (
              <p className="settings-hint">Edge TTS 免费无需 API Key，直接使用。</p>
            )}
          </>
        )}

        {!isCloud && (
          <p className="settings-hint">使用本地 ZipVoice INT8 模型（~126MB）。无需网络，延迟 ~2s。</p>
        )}
      </div>

      <div className="settings-row">
        <button type="button" className="control-btn control-btn--start" onClick={handleApply}
          disabled={!isValid} title={!isValid ? '请填写必填项' : '应用设置'}>
          {saved ? '✓ 已应用' : '应用'}
        </button>
      </div>
    </div>
  );
}