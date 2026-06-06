/** Settings store — persisted to localStorage via zustand. */
import { create } from 'zustand';
import type { AppSettings, LLMConfig, LLMProvider, AsrConfig, AsrProvider } from '../types/config';
import { DEFAULT_SETTINGS, LLM_PROVIDERS, ASR_PROVIDERS } from '../types/config';

const KEY = 'ai-translate-settings';

function load(): AppSettings {
  try { const raw = localStorage.getItem(KEY); if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }; } catch { /* */ }
  return { ...DEFAULT_SETTINGS };
}
function save(s: AppSettings): void {
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* */ }
}

interface SettingsStore extends AppSettings {
  // LLM
  setLLMConfig: (c: Partial<LLMConfig>) => void;
  setProvider: (p: LLMProvider) => void;
  setApiKey: (k: string) => void;
  setModel: (m: string) => void;
  setBaseUrl: (u: string) => void;
  setLLMEnabled: (e: boolean) => void;
  // ASR
  setAsrProvider: (p: AsrProvider) => void;
  setAsrApiKey: (k: string) => void;
  setAsrApiSecret: (s: string) => void;
  setAsrBaseUrl: (u: string) => void;
  reset: () => void;
}

export const useSettingsStore = create<SettingsStore>((set, get) => {
  const init = load();
  return {
    ...init,
    // LLM
    setLLMConfig: (c) => set((s) => { const n = { ...s, llm: { ...s.llm, ...c } }; save(n); return n; }),
    setProvider: (p) => set((s) => {
      const info = LLM_PROVIDERS.find((x) => x.id === p);
      const n = { ...s, llm: { ...s.llm, provider: p, model: info?.defaultModel ?? '', baseUrl: info?.defaultBaseUrl ?? '' } };
      save(n); return n;
    }),
    setApiKey: (apiKey) => set((s) => { const n = { ...s, llm: { ...s.llm, apiKey } }; save(n); return n; }),
    setModel: (model) => set((s) => { const n = { ...s, llm: { ...s.llm, model } }; save(n); return n; }),
    setBaseUrl: (baseUrl) => set((s) => { const n = { ...s, llm: { ...s.llm, baseUrl } }; save(n); return n; }),
    setLLMEnabled: (enabled) => set((s) => { const n = { ...s, llm: { ...s.llm, enabled } }; save(n); return n; }),
    // ASR
    setAsrProvider: (p) => set((s) => {
      const info = ASR_PROVIDERS.find((x) => x.id === p);
      const n = { ...s, asr: { ...s.asr, provider: p, baseUrl: info?.defaultBaseUrl ?? '' } };
      save(n); return n;
    }),
    setAsrApiKey: (apiKey) => set((s) => { const n = { ...s, asr: { ...s.asr, apiKey } }; save(n); return n; }),
    setAsrApiSecret: (apiSecret) => set((s) => { const n = { ...s, asr: { ...s.asr, apiSecret } }; save(n); return n; }),
    setAsrBaseUrl: (baseUrl) => set((s) => { const n = { ...s, asr: { ...s.asr, baseUrl } }; save(n); return n; }),
    reset: () => { set(DEFAULT_SETTINGS); save(DEFAULT_SETTINGS); },
  };
});
