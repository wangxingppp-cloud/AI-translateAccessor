/**
 * LLM provider configuration panel.
 * - Choose provider (OpenAI/Claude/DeepSeek/Custom)
 * - Free text API Key + model name input
 * - Test connection button
 * - Toggle LLM correction on/off
 */
import { useState } from 'react';
import { useSettingsStore } from '../../stores/settingsStore';
import { LLM_PROVIDERS } from '../../types/config';

type TestStatus = 'idle' | 'testing' | 'success' | 'error';

export function ModelSettings() {
  const { llm, setProvider, setApiKey, setModel, setBaseUrl, setLLMEnabled } = useSettingsStore();
  const [testStatus, setTestStatus] = useState<TestStatus>('idle');
  const [testMessage, setTestMessage] = useState('');

  const handleTest = async () => {
    if (!llm.apiKey.trim()) { setTestStatus('error'); setTestMessage('请先填入 API Key'); return; }
    if (!llm.model.trim()) { setTestStatus('error'); setTestMessage('请先填入模型名称'); return; }
    setTestStatus('testing'); setTestMessage('');

    try {
      const base = llm.baseUrl.replace(/\/+$/, '');
      const isAnthro = llm.provider === 'anthropic';
      const endpoint = isAnthro ? `${base}/v1/messages` : `${base}/chat/completions`;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (isAnthro) { headers['x-api-key'] = llm.apiKey; headers['anthropic-version'] = '2023-06-01'; }
      else { headers['Authorization'] = `Bearer ${llm.apiKey}`; }
      const body = JSON.stringify({ model: llm.model, max_tokens: 10, messages: [{ role: 'user', content: 'hi' }] });

      const resp = await fetch(endpoint, { method: 'POST', headers, body, signal: AbortSignal.timeout(15000) });
      if (resp.ok) { setTestStatus('success'); setTestMessage(`连接成功 — 模型 "${llm.model}" 可用`); }
      else {
        const err = await resp.text().catch(() => '').then((t) => t.slice(0, 200));
        if (resp.status === 401 || resp.status === 403) setTestMessage('API Key 无效或被拒绝');
        else if (resp.status === 404) setTestMessage(`模型 "${llm.model}" 未找到`);
        else setTestMessage(`请求失败 (${resp.status}): ${err}`);
        setTestStatus('error');
      }
    } catch (e: unknown) {
      const msg = (e as Error).message || '';
      if (msg.includes('timeout') || msg.includes('AbortError')) setTestMessage('连接超时，请检查 API 地址和网络');
      else if (msg.includes('Failed to fetch')) setTestMessage('无法连接到服务器，请检查 API 地址');
      else setTestMessage(msg);
      setTestStatus('error');
    }
  };

  const clear = () => { setTestStatus('idle'); setTestMessage(''); };

  return (
    <div className="settings-section">
      <h3 className="settings-section__title">LLM 翻译修正</h3>
      <p className="settings-section__desc">AI 大模型异步修正 NMT 初译结果。API Key 仅存储在本地。</p>

      <div className="settings-row">
        <label className="settings-label">启用 LLM 修正</label>
        <button type="button" className={`toggle ${llm.enabled ? 'toggle--on' : ''}`} onClick={() => setLLMEnabled(!llm.enabled)} role="switch" aria-checked={llm.enabled}>
          <span className="toggle__knob" />
        </button>
      </div>
      {!llm.enabled && <p className="settings-hint">LLM 修正已关闭，仅使用 NMT 初译。</p>}

      <div className={`settings-body ${!llm.enabled ? 'settings-body--disabled' : ''}`}>
        <div className="settings-row">
          <label className="settings-label">供应商</label>
          <div className="provider-grid">
            {LLM_PROVIDERS.map((p) => (
              <button key={p.id} type="button" className={`provider-card ${llm.provider === p.id ? 'provider-card--active' : ''}`} onClick={() => { setProvider(p.id); clear(); }} title={p.description}>
                <span className="provider-card__name">{p.name}</span>
                <span className="provider-card__desc">{p.description}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="llm-api-key">API Key</label>
          <input id="llm-api-key" type="password" className="settings-input" value={llm.apiKey} onChange={(e) => { setApiKey(e.target.value); clear(); }} placeholder="输入 API Key" />
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="llm-model">模型名称</label>
          <input id="llm-model" type="text" className="settings-input" value={llm.model} onChange={(e) => { setModel(e.target.value); clear(); }} placeholder="如 gpt-4o-mini, claude-haiku-4-5, deepseek-chat" />
          <p className="settings-hint">参考: {LLM_PROVIDERS.find((p) => p.id === llm.provider)?.models.join(', ') || '输入任意模型名'}</p>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="llm-base-url">API 地址</label>
          <input id="llm-base-url" type="text" className="settings-input" value={llm.baseUrl} onChange={(e) => { setBaseUrl(e.target.value); clear(); }} />
        </div>

        <div className="settings-row">
          <div className="test-row">
            <button type="button" className="test-btn" onClick={handleTest} disabled={testStatus === 'testing'}>
              {testStatus === 'testing' ? '⏳ 测试中...' : '🔍 测试连接'}
            </button>
            {testStatus === 'success' && <span className="test-msg test-msg--ok">{testMessage}</span>}
            {testStatus === 'error' && <span className="test-msg test-msg--err">{testMessage}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
