/** Application configuration types. Settings are persisted locally. */

// ── LLM (translation correction) ──────────────────────────────

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

export const LLM_PROVIDERS: LLMProviderInfo[] = [
  { id: 'openai', name: 'OpenAI', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'], defaultModel: 'gpt-4o-mini', defaultBaseUrl: 'https://api.openai.com/v1', description: 'GPT-4o / GPT-4o-mini — 翻译质量高，速度快' },
  { id: 'anthropic', name: 'Anthropic Claude', models: ['claude-sonnet-4-6', 'claude-haiku-4-5'], defaultModel: 'claude-haiku-4-5', defaultBaseUrl: 'https://api.anthropic.com', description: 'Claude Sonnet/Haiku — 上下文理解强' },
  { id: 'deepseek', name: 'DeepSeek', models: ['deepseek-chat', 'deepseek-reasoner'], defaultModel: 'deepseek-chat', defaultBaseUrl: 'https://api.deepseek.com/v1', description: 'DeepSeek V3/R1 — 性价比高，中文强' },
  { id: 'custom', name: '自定义', models: [], defaultModel: '', defaultBaseUrl: '', description: 'OpenAI 兼容接口（Ollama、vLLM）' },
];

// ── ASR (speech recognition) ──────────────────────────────────

export type AsrProvider = 'local' | 'iflytek' | 'baidu';

export interface AsrProviderInfo {
  id: AsrProvider;
  name: string;
  description: string;
  needsApiKey: boolean;
  latency: string;
  cost: string;
  defaultBaseUrl: string;
}

export interface AsrConfig {
  provider: AsrProvider;
  apiKey: string;
  apiSecret: string;  // 讯飞/百度需要 AppSecret
  appId: string;      // 讯飞需要 APPID
  baseUrl: string;
}

export const ASR_PROVIDERS: AsrProviderInfo[] = [
  { id: 'local', name: '本地离线', description: 'SenseVoice 多语种 — 免费，延迟 ~2s，无需网络', needsApiKey: false, latency: '~2s', cost: '免费', defaultBaseUrl: '' },
  { id: 'iflytek', name: '讯飞', description: '流式 ASR — 延迟 ~200ms，中文最佳，需实名认证', needsApiKey: true, latency: '~200ms', cost: '0.008-0.02 元/分钟', defaultBaseUrl: 'wss://office-api-ast-dx.iflyaisol.com/ast/communicate/v1' },
  { id: 'baidu', name: '百度', description: '流式 ASR — 延迟 ~300ms，多语种支持好', needsApiKey: true, latency: '~300ms', cost: '0.006-0.015 元/分钟', defaultBaseUrl: 'https://vop.baidu.com/server_api' },
];

// ── Languages ─────────────────────────────────────────────────

export const SOURCE_LANGS = [
  { code: 'en', name: 'English', label: '英语' },
  { code: 'ja', name: 'Japanese', label: '日语' },
  { code: 'ko', name: 'Korean', label: '韩语' },
  { code: 'yue', name: 'Cantonese', label: '粤语' },
  { code: 'zh', name: 'Chinese', label: '中文' },
];

export const TARGET_LANGS = [
  { code: 'zh', name: 'Chinese', label: '中文' },
  { code: 'en', name: 'English', label: '英语' },
];

// ── App Settings ──────────────────────────────────────────────

export interface AppSettings {
  llm: LLMConfig;
  asr: AsrConfig;
  sourceLang: string;
  targetLang: string;
}

export const DEFAULT_SETTINGS: AppSettings = {
  llm: { provider: 'openai', apiKey: '', model: 'gpt-4o-mini', baseUrl: 'https://api.openai.com/v1', enabled: false },
  asr: { provider: 'local', apiKey: '', apiSecret: '', appId: '', baseUrl: '' },
  sourceLang: 'en', targetLang: 'zh',
};
