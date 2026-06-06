/**
 * Settings store — persisted to localStorage.
 *
 * Stores LLM configuration, language preferences, and other user settings.
 * The LLM config (apiKey, provider, model) is sent to the backend
 * via WebSocket control message when a session starts.
 */
import { create } from 'zustand';
import type { AppSettings, LLMConfig, LLMProvider } from '../types/config';
import { DEFAULT_SETTINGS, LLM_PROVIDERS } from '../types/config';

const STORAGE_KEY = 'ai-translate-settings';

function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
    }
  } catch { /* ignore corrupt data */ }
  return { ...DEFAULT_SETTINGS };
}

function saveSettings(settings: AppSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch { /* ignore */ }
}

interface SettingsStore extends AppSettings {
  /** Update the entire LLM configuration. */
  setLLMConfig: (config: Partial<LLMConfig>) => void;
  /** Update a single LLM field. */
  setProvider: (provider: LLMProvider) => void;
  setApiKey: (key: string) => void;
  setModel: (model: string) => void;
  setBaseUrl: (url: string) => void;
  setLLMEnabled: (enabled: boolean) => void;
  /** Get the provider info for the current selection. */
  getProviderInfo: () => (typeof LLM_PROVIDERS)[0] | undefined;
  /** Reset all settings to defaults. */
  reset: () => void;
}

export const useSettingsStore = create<SettingsStore>((set, get) => {
  const initial = loadSettings();

  return {
    ...initial,

    setLLMConfig: (config) =>
      set((s) => {
        const next = { ...s, llm: { ...s.llm, ...config } };
        saveSettings(next);
        return next;
      }),

    setProvider: (provider) => {
      const info = LLM_PROVIDERS.find((p) => p.id === provider);
      set((s) => {
        const next = {
          ...s,
          llm: {
            ...s.llm,
            provider,
            model: info?.defaultModel ?? '',
            baseUrl: info?.defaultBaseUrl ?? '',
          },
        };
        saveSettings(next);
        return next;
      });
    },

    setApiKey: (apiKey) => {
      set((s) => {
        const next = { ...s, llm: { ...s.llm, apiKey } };
        saveSettings(next);
        return next;
      });
    },

    setModel: (model) => {
      set((s) => {
        const next = { ...s, llm: { ...s.llm, model } };
        saveSettings(next);
        return next;
      });
    },

    setBaseUrl: (baseUrl) => {
      set((s) => {
        const next = { ...s, llm: { ...s.llm, baseUrl } };
        saveSettings(next);
        return next;
      });
    },

    setLLMEnabled: (enabled) => {
      set((s) => {
        const next = { ...s, llm: { ...s.llm, enabled } };
        saveSettings(next);
        return next;
      });
    },

    getProviderInfo: () => LLM_PROVIDERS.find((p) => p.id === get().llm.provider),

    reset: () => {
      set(DEFAULT_SETTINGS);
      saveSettings(DEFAULT_SETTINGS);
    },
  };
});
