# AI 同声传译助手 — 前端

基于 React + TypeScript + Electron 的实时同声传译桌面应用前端。

## 技术栈

### 前端

| 类别 | 技术 | 说明 |
|------|------|------|
| UI 框架 | React 19 + TypeScript 6 | 组件化 UI 开发 |
| 构建工具 | Vite 8 | 开发服务器 + 生产构建 |
| 桌面壳 | Electron 41 | 跨平台桌面应用（Windows / macOS / Linux） |
| 状态管理 | Zustand 5 | 轻量级状态管理，设置项持久化到 localStorage |
| 图标库 | Lucide React | 矢量图标组件 |
| 打包工具 | electron-builder | 生成 NSIS 安装包 / 便携版 / DMG |
| 音频采集 | Web Audio API | 麦克风录音（ScriptProcessorNode） |
| 系统音频 | WASAPI Loopback (C#/.NET 9 + NAudio) | Windows 系统音频捕获辅助程序 |

### 后端

| 类别 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI + Uvicorn | 异步高性能 Python Web 框架 |
| 实时通信 | WebSocket (FastAPI) | 实时音频流传输与字幕推送 |
| 数据库 | SQLAlchemy 2 (async) + aiosqlite | SQLite 异步 ORM |
| 数据验证 | Pydantic 2 + pydantic-settings | 请求/响应模型验证 + 环境变量配置 |
| 本地 ASR | sherpa-onnx | SenseVoice（多语言离线）/ Zipformer（流式英文）/ Paraformer（流式中文） |
| 云端 ASR | 讯飞 RTASR/IAT、百度 | 云端实时语音识别 WebSocket API |
| LLM 翻译 | openai SDK | 支持 OpenAI / Anthropic / DeepSeek / 自定义 OpenAI 兼容端点 |
| 本地 TTS | sherpa-onnx ZipVoice | 离线中英文语音合成（INT8 量化） |
| 云端 TTS | edge-tts / OpenAI TTS | Microsoft Edge TTS（免费）/ OpenAI TTS API |
| 语音活动检测 | Silero VAD + 能量阈值 | 检测语音/静音段，驱动句子边界切分 |
| 日志 | Loguru | 结构化日志（文件轮转 + 彩色控制台） |
| 音频处理 | NumPy + soundfile | PCM 格式转换、重采样 |
| 缓存 | Redis (可选) | 多 Worker 场景下的共享缓存 |
| 路径管理 | platformdirs | 跨平台用户数据目录 |
| 打包工具 | PyInstaller | 后端打包为独立可执行文件 |

### AI 模型

| 模型 | 用途 | 来源 |
|------|------|------|
| sherpa-onnx SenseVoice | 多语言离线 ASR（中/英/日/韩/粤） | 本地位于 `models/sherpa-onnx-paraformer/` |
| sherpa-onnx Zipformer | 流式英文 ASR | 本地位于 `models/sherpa-onnx-zipformer/` |
| sherpa-onnx Paraformer | 流式中文 ASR | 本地位于 `models/sherpa-onnx-paraformer/` |
| Silero VAD | 语音活动检测 | 本地位于 `models/silero-vad/` |
| sherpa-onnx ZipVoice | 离线中英文 TTS（零样本语音克隆） | 本地位于 `models/sherpa-onnx-zipvoice-.../` |

## 目录结构

```
frontend/
├── electron/                       # Electron 主进程
│   ├── main.ts                     # 窗口创建、IPC 注册、后端生命周期管理
│   ├── preload.cjs                 # Context Bridge（窗口控制、音频、后端 IPC）
│   ├── backend.ts                  # Python 后端子进程管理（启动、端口发现）
│   ├── ipc/
│   │   └── audio.ts                # 音频 IPC 通道注册
│   └── audio/
│       ├── types.ts                # SystemAudioCapturer 接口定义
│       ├── windows.ts              # Windows: 启动 wasapi-capture.exe
│       ├── macos.ts                # macOS: sox / BlackHole
│       └── linux.ts                # Linux: PulseAudio / PipeWire
│
├── resources/
│   └── wasapi-capture/             # C# .NET 9 NAudio WASAPI 系统音频采集辅助程序
│
├── src/
│   ├── main.tsx                    # React 入口 + ErrorBoundary
│   ├── App.tsx                     # 主应用组件（UI 编排）
│   ├── App.css                     # 设计系统（赛博朋克暗色主题）
│   │
│   ├── components/
│   │   ├── audio/
│   │   │   ├── AudioSourceSelector.tsx   # 麦克风 / 系统音频切换
│   │   │   ├── AudioControls.tsx         # 开始 / 暂停 / 恢复 / 停止 + 保存对话框
│   │   │   └── AudioVisualizer.tsx       # Canvas 音频电平指示器
│   │   ├── subtitle/
│   │   │   ├── SubtitleList.tsx          # 自动滚动字幕列表
│   │   │   └── SubtitleLine.tsx          # 单行字幕（diff 高亮 + TTS 播放）
│   │   ├── settings/
│   │   │   ├── SettingsPanel.tsx         # 设置面板（ASR / LLM / TTS 三个 Tab）
│   │   │   ├── AsrSettings.tsx           # ASR 提供商配置
│   │   │   ├── ModelSettings.tsx         # LLM 翻译校正配置
│   │   │   └── TtsSettings.tsx           # TTS 配置
│   │   ├── history/
│   │   │   └── HistoryPanel.tsx          # 翻译历史浏览与搜索
│   │   └── glossary/
│   │       └── GlossaryManager.tsx       # 术语表管理（创建 / 查看 / 删除）
│   │
│   ├── hooks/
│   │   ├── useWebSocket.ts              # WebSocket 生命周期 Hook
│   │   └── useAudioCapture.ts           # 音频采集生命周期 Hook
│   │
│   ├── services/
│   │   ├── websocket-client.ts          # WebSocket 客户端（自动重连 + 心跳 + 二进制音频发送）
│   │   ├── audio-capture.ts             # 音频采集服务（麦克风 Web Audio API + 系统音频 Electron IPC）
│   │   └── tts-client.ts                # TTS 客户端（HTTP POST + 内存缓存）
│   │
│   ├── stores/
│   │   ├── connectionStore.ts           # 连接状态（WebSocket + 后端）
│   │   ├── subtitleStore.ts             # 实时字幕条目（去重、校正、清空）
│   │   ├── settingsStore.ts             # 应用设置（LLM / ASR / TTS 配置，localStorage 持久化）
│   │   └── ttsStore.ts                  # TTS 播放管理（全局单例 AudioContext）
│   │
│   └── types/
│       ├── audio.ts                     # AudioSource, AudioFormat, AudioCaptureState
│       ├── config.ts                    # LLMProvider, AsrProvider, TtsProvider, AppSettings
│       ├── ws-messages.ts               # WebSocket 协议消息类型
│       └── electron.d.ts                # Electron API 类型声明
│
├── package.json
├── vite.config.ts
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
└── index.html
```

## 环境准备

### 前置要求

- **Node.js** >= 18
- **npm** >= 9

### 安装依赖

```bash
cd frontend
npm install
```

###（可选）编译 WASAPI 系统音频采集程序

仅 Windows 用户需要，用于捕获系统音频输出：

```bash
cd resources/wasapi-capture
dotnet publish -c Release -r win-x64 --self-contained
```

需要 .NET 9 SDK。编译产物用于 Electron 打包时自动复制到应用资源目录。

## 启动方式

### 浏览器开发模式

需要先单独启动后端服务（默认 `http://127.0.0.1:8000`）。

```bash
npm run dev
```

浏览器访问 `http://localhost:5173`。

### Electron 开发模式

```bash
npm run electron:dev
```

Vite 开发服务器 + Electron 窗口同时启动。后端需单独启动。

### Electron 预览模式

```bash
npm run electron:preview
```

先构建前端产物，再启动 Electron 窗口。

## 构建打包

```bash
# 构建安装包
npm run electron:build
```

构建产物位于 `release/` 目录：
- **Windows**: NSIS 安装包 + 便携版（`AI 同声传译 Setup x.x.x.exe`）
- **macOS**: DMG + ZIP

## 可用脚本

| 命令 | 说明 |
|------|------|
| `npm run dev` | 启动 Vite 开发服务器（浏览器模式） |
| `npm run build` | TypeScript 编译 + Vite 生产构建 |
| `npm run lint` | ESLint 代码检查 |
| `npm run preview` | 预览生产构建产物 |
| `npm run electron:dev` | Electron 开发模式 |
| `npm run electron:build` | 构建 Electron 安装包 |
| `npm run electron:preview` | Electron 预览模式 |

## 状态管理

使用 Zustand 管理全局状态，共 4 个 Store：

| Store | 文件 | 职责 |
|-------|------|------|
| `connectionStore` | `stores/connectionStore.ts` | WebSocket 连接状态、后端端口、后端错误信息 |
| `subtitleStore` | `stores/subtitleStore.ts` | 实时字幕条目（添加、校正、去重、清空） |
| `settingsStore` | `stores/settingsStore.ts` | 应用设置（LLM/ASR/TTS 配置），持久化到 localStorage |
| `ttsStore` | `stores/ttsStore.ts` | TTS 播放管理（全局单例 AudioContext，同一时间只播放一条） |

## 前后端通信

前端通过三种通道与后端交互：

1. **WebSocket** (`ws://127.0.0.1:{port}/ws/translate`) — 实时音频流 + 字幕推送
2. **REST API** (`http://127.0.0.1:{port}/api/...`) — 健康检查、TTS、历史记录、术语表
3. **Electron IPC** — 窗口控制、系统音频采集、后端生命周期
