/** Settings store — persisted to localStorage via zustand. */
import { create } from 'zustand';
import type { AppSettings, LLMConfig, LLMProvider, AsrConfig, AsrProvider, TtsConfig, TtsProvider } from '../types/config';
import { DEFAULT_SETTINGS, LLM_PROVIDERS, ASR_PROVIDERS, TTS_PROVIDERS } from '../types/config';

const KEY = 'ai-translate-settings';

function load(): AppSettings {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        ...DEFAULT_SETTINGS,
        ...parsed,
        asr: { ...DEFAULT_SETTINGS.asr, ...parsed.asr },
        llm: { ...DEFAULT_SETTINGS.llm, ...parsed.llm },
        tts: { ...DEFAULT_SETTINGS.tts, ...parsed.tts },
      };
    }
  } catch { /* */ }
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
  setAsrAppId: (a: string) => void;
  // TTS
  setTtsConfig: (c: Partial<TtsConfig>) => void;
  setTtsProvider: (p: TtsProvider) => void;
  setTtsApiKey: (k: string) => void;
  setTtsVoice: (v: string) => void;
  setTtsBaseUrl: (u: string) => void;
  setTtsEnabled: (e: boolean) => void;
  // Language
  setSourceLang: (l: string) => void;
  setTargetLang: (l: string) => void;
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
    setAsrAppId: (appId) => set((s) => { const n = { ...s, asr: { ...s.asr, appId } }; save(n); return n; }),
    // TTS
    setTtsConfig: (c) => set((s) => { const n = { ...s, tts: { ...s.tts, ...c } }; save(n); return n; }),
    setTtsProvider: (p) => set((s) => {
      const info = TTS_PROVIDERS.find((x) => x.id === p);
      const n = { ...s, tts: { ...s.tts, provider: p, voice: info?.defaultVoice ?? '', baseUrl: info?.defaultBaseUrl ?? '' } };
      save(n); return n;
    }),
    setTtsApiKey: (apiKey) => set((s) => { const n = { ...s, tts: { ...s.tts, apiKey } }; save(n); return n; }),
    setTtsVoice: (voice) => set((s) => { const n = { ...s, tts: { ...s.tts, voice } }; save(n); return n; }),
    setTtsBaseUrl: (baseUrl) => set((s) => { const n = { ...s, tts: { ...s.tts, baseUrl } }; save(n); return n; }),
    setTtsEnabled: (enabled) => set((s) => { const n = { ...s, tts: { ...s.tts, enabled } }; save(n); return n; }),
    setSourceLang: (sourceLang) => set((s) => { const n = { ...s, sourceLang }; save(n); return n; }),
    setTargetLang: (targetLang) => set((s) => { const n = { ...s, targetLang }; save(n); return n; }),
    reset: () => { set(DEFAULT_SETTINGS); save(DEFAULT_SETTINGS); },
  };
});
