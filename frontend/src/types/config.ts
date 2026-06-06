/** Application configuration types. Settings are persisted locally. */
export type LLMProvider = 'openai' | 'anthropic' | 'deepseek' | 'custom';

export interface LLMProviderInfo {
  id: LLMProvider;
  name: string;
  models: string[];
  defaultModel: string;
  defaultBaseUrl: string;
  description: string;
}

export interface LLMConfig {
  provider: LLMProvider;
  apiKey: string;
  model: string;
  baseUrl: string;
  enabled: boolean;
}

export interface AppSettings {
  llm: LLMConfig;
  sourceLang: string;
  targetLang: string;
}

export const LLM_PROVIDERS: LLMProviderInfo[] = [
  {
    id: 'openai', name: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
    defaultModel: 'gpt-4o-mini',
    defaultBaseUrl: 'https://api.openai.com/v1',
    description: 'GPT-4o / GPT-4o-mini — 翻译质量高，速度快',
  },
  {
    id: 'anthropic', name: 'Anthropic Claude',
    models: ['claude-sonnet-4-6', 'claude-haiku-4-5'],
    defaultModel: 'claude-haiku-4-5',
    defaultBaseUrl: 'https://api.anthropic.com',
    description: 'Claude Sonnet/Haiku — 上下文理解强，适合长文修正',
  },
  {
    id: 'deepseek', name: 'DeepSeek',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    defaultModel: 'deepseek-chat',
    defaultBaseUrl: 'https://api.deepseek.com/v1',
    description: 'DeepSeek V3/R1 — 性价比高，中文能力强',
  },
  {
    id: 'custom', name: '自定义',
    models: [],
    defaultModel: '',
    defaultBaseUrl: '',
    description: '自定义 OpenAI 兼容接口（Ollama、vLLM 等）',
  },
];

export const DEFAULT_SETTINGS: AppSettings = {
  llm: { provider: 'openai', apiKey: '', model: 'gpt-4o-mini', baseUrl: 'https://api.openai.com/v1', enabled: false },
  sourceLang: 'en', targetLang: 'zh',
};
