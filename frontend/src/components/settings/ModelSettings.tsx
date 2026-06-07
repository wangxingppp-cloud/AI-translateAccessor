/**
 * LLM provider configuration with local draft + Apply button + test.
 */
import { useState } from 'react';
import { useSettingsStore } from '../../stores/settingsStore';
import { LLM_PROVIDERS, type LLMConfig } from '../../types/config';

type TestStatus = 'idle' | 'testing' | 'success' | 'error';

export function ModelSettings() {
  const storedLlm = useSettingsStore((s) => s.llm);
  const setLLMConfig = useSettingsStore((s) => s.setLLMConfig);

  const [draft, setDraft] = useState<LLMConfig>({ ...storedLlm });
  const [saved, setSaved] = useState(false);
  const [testStatus, setTestStatus] = useState<TestStatus>('idle');
  const [testMessage, setTestMessage] = useState('');

  const isValid = !draft.enabled || (draft.apiKey.trim() && draft.model.trim());

  const handleApply = () => {
    setLLMConfig(draft);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleTest = async () => {
    if (!draft.apiKey.trim()) { setTestStatus('error'); setTestMessage('请先填入 API Key'); return; }
    if (!draft.model.trim()) { setTestStatus('error'); setTestMessage('请先填入模型名称'); return; }
    setTestStatus('testing'); setTestMessage('');
    try {
      const base = draft.baseUrl.replace(/\/+$/, '');
      const isAnthro = draft.provider === 'anthropic';
      const endpoint = isAnthro ? `${base}/v1/messages` : `${base}/chat/completions`;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (isAnthro) { headers['x-api-key'] = draft.apiKey; headers['anthropic-version'] = '2023-06-01'; }
      else { headers['Authorization'] = `Bearer ${draft.apiKey}`; }
      const resp = await fetch(endpoint, {
        method: 'POST', headers,
        body: JSON.stringify({ model: draft.model, max_tokens: 10, messages: [{ role: 'user', content: 'hi' }] }),
        signal: AbortSignal.timeout(15000),
      });
      if (resp.ok) { setTestStatus('success'); setTestMessage(`连接成功 — 模型 "${draft.model}" 可用`); }
      else {
        const err = await resp.text().catch(() => '').then((t) => t.slice(0, 200));
        if (resp.status === 401 || resp.status === 403) setTestMessage('API Key 无效或被拒绝');
        else if (resp.status === 404) setTestMessage(`模型 "${draft.model}" 未找到`);
        else setTestMessage(`请求失败 (${resp.status}): ${err}`);
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
      <h3 className="settings-section__title">LLM 翻译修正</h3>
      <p className="settings-section__desc">AI 大模型翻译与修正。API Key 仅存储在本地。</p>

      <div className="settings-row">
        <label className="settings-label">启用 LLM 修正</label>
        <button type="button" className={`toggle ${draft.enabled ? 'toggle--on' : ''}`}
          onClick={() => setDraft((d) => ({ ...d, enabled: !d.enabled }))}
          role="switch" aria-checked={draft.enabled}>
          <span className="toggle__knob" />
        </button>
      </div>
      {!draft.enabled && <p className="settings-hint">LLM 已关闭，翻译将返回原文。</p>}

      <div className={`settings-body ${!draft.enabled ? 'settings-body--disabled' : ''}`}>
        <div className="settings-row">
          <label className="settings-label">供应商</label>
          <div className="provider-grid">
            {LLM_PROVIDERS.map((p) => (
              <button key={p.id} type="button"
                className={`provider-card ${draft.provider === p.id ? 'provider-card--active' : ''}`}
                onClick={() => setDraft((d) => ({ ...d, provider: p.id, model: p.defaultModel, baseUrl: p.defaultBaseUrl }))}>
                <span className="provider-card__name">{p.name}</span>
                <span className="provider-card__desc">{p.description}</span>
                {storedLlm.enabled && p.id === storedLlm.provider && <span className="provider-card__badge">使用中</span>}
              </button>
            ))}
          </div>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="llm-api-key">API Key</label>
          <input id="llm-api-key" type="password" className="settings-input"
            value={draft.apiKey} onChange={(e) => setDraft((d) => ({ ...d, apiKey: e.target.value }))}
            placeholder="输入 API Key" />
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="llm-model">模型名称</label>
          <input id="llm-model" type="text" className="settings-input"
            value={draft.model} onChange={(e) => setDraft((d) => ({ ...d, model: e.target.value }))}
            placeholder="如 gpt-4o-mini" />
          <p className="settings-hint">参考: {LLM_PROVIDERS.find((p) => p.id === draft.provider)?.models.join(', ') || '输入任意模型名'}</p>
        </div>

        <div className="settings-row">
          <label className="settings-label" htmlFor="llm-base-url">API 地址</label>
          <input id="llm-base-url" type="text" className="settings-input"
            value={draft.baseUrl} onChange={(e) => setDraft((d) => ({ ...d, baseUrl: e.target.value }))} />
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

      <div className="settings-row">
        <button type="button" className="control-btn control-btn--start" onClick={handleApply}
          disabled={!isValid} title={!isValid && draft.enabled ? '启用后需要填写 API Key 和模型名称' : '应用设置'}>
          {saved ? '✓ 已应用' : '应用'}
        </button>
      </div>
    </div>
  );
}
