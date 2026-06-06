/**
 * ASR provider configuration — local offline vs cloud API.
 */
import { useState } from 'react';
import { useSettingsStore } from '../../stores/settingsStore';
import { ASR_PROVIDERS, type AsrProvider } from '../../types/config';

type TestStatus = 'idle' | 'testing' | 'success' | 'error';

export function AsrSettings() {
  const { asr, setAsrProvider, setAsrApiKey, setAsrApiSecret, setAsrBaseUrl } = useSettingsStore();
  const [testStatus, setTestStatus] = useState<TestStatus>('idle');
  const [testMsg, setTestMsg] = useState('');

  const providerInfo = ASR_PROVIDERS.find((p) => p.id === asr.provider);
  const isCloud = asr.provider !== 'local';

  const handleProviderChange = (p: AsrProvider) => {
    setAsrProvider(p);
    setTestStatus('idle');
    setTestMsg('');
  };

  const handleTest = async () => {
    if (!asr.apiKey.trim()) { setTestStatus('error'); setTestMsg('请先填入 API Key'); return; }
    setTestStatus('testing'); setTestMsg('');
    // Cloud API test will be implemented when backend supports it
    setTimeout(() => { setTestStatus('success'); setTestMsg('API 测试暂未接入后端，请启动翻译后验证'); }, 500);
  };

  return (
    <div className="settings-section">
      <h3 className="settings-section__title">语音识别 (ASR)</h3>
      <p className="settings-section__desc">选择语音识别引擎。本地离线免费但延迟较高，云端 API 低延迟按量付费。</p>

      {/* Provider selection */}
      <div className="settings-row">
        <label className="settings-label">识别引擎</label>
        <div className="provider-grid">
          {ASR_PROVIDERS.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`provider-card ${asr.provider === p.id ? 'provider-card--active' : ''}`}
              onClick={() => handleProviderChange(p.id)}
            >
              <span className="provider-card__name">{p.name}</span>
              <span className="provider-card__desc">{p.description}</span>
              <span className="provider-card__meta">
                {p.latency} &middot; {p.cost}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Cloud API config */}
      {isCloud && (
        <div className="settings-body">
          <div className="settings-row">
            <label className="settings-label" htmlFor="asr-api-key">API Key</label>
            <input
              id="asr-api-key" type="password" className="settings-input"
              value={asr.apiKey}
              onChange={(e) => { setAsrApiKey(e.target.value); setTestStatus('idle'); }}
              placeholder={asr.provider === 'iflytek' ? '讯飞 API Key' : '百度 API Key'}
            />
          </div>

          <div className="settings-row">
            <label className="settings-label" htmlFor="asr-api-secret">API Secret</label>
            <input
              id="asr-api-secret" type="password" className="settings-input"
              value={asr.apiSecret}
              onChange={(e) => { setAsrApiSecret(e.target.value); setTestStatus('idle'); }}
              placeholder={asr.provider === 'iflytek' ? '讯飞 API Secret' : '百度 Secret Key'}
            />
          </div>

          <div className="settings-row">
            <label className="settings-label" htmlFor="asr-base-url">API 地址</label>
            <input
              id="asr-base-url" type="text" className="settings-input"
              value={asr.baseUrl}
              onChange={(e) => { setAsrBaseUrl(e.target.value); setTestStatus('idle'); }}
              placeholder={providerInfo?.defaultBaseUrl}
            />
            <p className="settings-hint">默认: {providerInfo?.defaultBaseUrl || '无需配置'}</p>
          </div>

          <div className="settings-row">
            <div className="test-row">
              <button type="button" className="test-btn" onClick={handleTest} disabled={testStatus === 'testing'}>
                {testStatus === 'testing' ? '⏳ 测试中...' : '🔍 测试连接'}
              </button>
              {testStatus === 'success' && <span className="test-msg test-msg--ok">{testMsg}</span>}
              {testStatus === 'error' && <span className="test-msg test-msg--err">{testMsg}</span>}
            </div>
          </div>
        </div>
      )}

      {!isCloud && (
        <p className="settings-hint">使用本地 SenseVoice 多语种模型（228MB）。无需网络，延迟 ~2s。</p>
      )}
    </div>
  );
}
