# AI 同声传译助手

AI 同声传译助手 — 实时语音识别、翻译与字幕显示桌面应用。帮助用户在观看外语音视频、参加线上会议时获得实时翻译字幕。

## 功能特性

- **实时语音识别** — 支持本地离线 ASR（sherpa-onnx SenseVoice / Zipformer / Paraformer）和云端 ASR（讯飞 RTASR、讯飞 IAT、百度）
- **LLM 翻译与校正** — 支持 OpenAI、Anthropic、DeepSeek 及任意 OpenAI 兼容端点（Ollama、vLLM 等），异步校正翻译结果并展示 diff 高亮
- **系统音频采集** — Windows 下通过 WASAPI Loopback 捕获系统音频，无需虚拟声卡
- **文本转语音** — 支持本地离线 TTS（sherpa-onnx ZipVoice）、Edge TTS、OpenAI TTS
- **术语表管理** — 自定义领域术语，LLM 校正时自动注入保持翻译一致性
- **翻译历史** — SQLite 持久化所有会话与字幕记录，支持全文搜索
- **桌面应用** — Electron 桌面壳，无边框窗口，置顶显示，支持 Windows / macOS / Linux

## 项目架构

```
AI-translateAccessor/
├── build.bat                         # Windows 一键打包脚本
├── build.sh                          # macOS/Linux 一键打包脚本（未测试）
│
├── backend/                          # Python FastAPI 后端
│   ├── launcher.py                   # PyInstaller 打包入口
│   ├── ai-translate-backend.spec     # PyInstaller 打包配置（含 hidden imports）
│   ├── requirements.txt              # Python 依赖
│   ├── Dockerfile                    # Docker 镜像构建文件
│   ├── docker-compose.yml            # Docker 部署配置（后端 + Redis）
│   ├── .env.example                  # 环境变量模板
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI 应用工厂 + uvicorn 启动入口
│   │   ├── config.py                 # Pydantic Settings 配置中心（23 个环境变量）
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── ws.py                 # WebSocket /ws/translate 实时翻译管道
│   │   │   └── rest.py               # REST API（健康检查、TTS、历史、术语表）
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── session_manager.py    # 会话状态机（IDLE/LISTENING/PAUSED/ERROR/ENDED）
│   │   │   ├── connection_manager.py # WebSocket 连接管理
│   │   │   └── audio_buffer.py       # 音频环形缓冲区
│   │   ├── engines/
│   │   │   ├── __init__.py
│   │   │   ├── asr/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── sherpa_engine.py       # 本地 ASR 引擎（SenseVoice/Zipformer/Paraformer）
│   │   │   │   ├── cloud_asr.py           # 云端 ASR（讯飞 RTASR/IAT、百度）
│   │   │   │   ├── audio_capture.py       # Windows WASAPI Loopback 系统音频采集
│   │   │   │   ├── ring_buffer.py         # 30 秒环形缓冲区
│   │   │   │   ├── mark_processor.py      # VAD 标记生成器
│   │   │   │   ├── transcription_worker.py# 后台转录工作线程
│   │   │   │   ├── stream_handler.py      # 流式 ASR 句子边界检测
│   │   │   │   └── vad_processor.py       # 语音活动检测（能量阈值）
│   │   │   ├── correction/
│   │   │   │   ├── __init__.py
│   │   │   │   └── corrector.py           # LLM 翻译校正引擎（带上下文 + 术语表）
│   │   │   ├── translation/
│   │   │   │   ├── __init__.py
│   │   │   │   └── context_manager.py     # 滑动窗口翻译上下文
│   │   │   └── tts/
│   │   │       ├── __init__.py
│   │   │       └── tts_engine.py          # 离线 TTS（sherpa-onnx ZipVoice）
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py           # SQLAlchemy async SQLite + 迁移
│   │   │   ├── models.py             # ORM 模型（Session, Subtitle, Glossary, GlossaryTerm）
│   │   │   └── repositories/
│   │   │       └── __init__.py       # 数据仓库（预留）
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── subtitle.py           # SubtitleDraft, SubtitleCorrected, DiffSegment
│   │   │   ├── session.py            # SessionCreate, SessionStatus
│   │   │   └── glossary.py           # Glossary, Term
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── history_service.py    # 翻译历史 CRUD
│   │   │   └── glossary_service.py   # 术语表 CRUD
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── logger.py             # Loguru 日志配置
│   │       └── metrics.py            # 管道延迟指标
│   └── tests/
│       └── __init__.py               # 测试包（预留）
│
├── frontend/                         # React + Electron 前端
│   ├── package.json                  # 依赖与构建脚本
│   ├── vite.config.ts                # Vite + Electron 插件配置
│   ├── index.html                    # Vite 入口 HTML
│   ├── tsconfig.json                 # 根 TypeScript 配置
│   ├── tsconfig.app.json             # React 应用 TS 配置
│   ├── tsconfig.node.json            # Electron/Node TS 配置
│   ├── eslint.config.js              # ESLint 配置
│   ├── electron/
│   │   ├── main.ts                   # Electron 主进程（窗口、IPC、后端生命周期）
│   │   ├── preload.cjs               # Context Bridge（窗口控制、音频 IPC）
│   │   ├── backend.ts                # Python 后端进程管理（启动、端口发现、模型路径）
│   │   ├── ipc/
│   │   │   ├── index.ts              # IPC 导出
│   │   │   └── audio.ts              # 音频 IPC 通道
│   │   └── audio/
│   │       ├── index.ts              # 平台音频采集器工厂
│   │       ├── types.ts              # SystemAudioCapturer 接口
│   │       ├── windows.ts            # Windows: 启动 wasapi-capture.exe
│   │       ├── macos.ts              # macOS: sox/BlackHole
│   │       └── linux.ts              # Linux: PulseAudio/PipeWire
│   ├── resources/
│   │   └── wasapi-capture/           # C# .NET 9 NAudio WASAPI 辅助程序源码
│   │   └── wasapi-capture-bin/       # 编译产物（.exe + DLL）
│   ├── src/
│   │   ├── main.tsx                  # React 入口 + ErrorBoundary
│   │   ├── App.tsx                   # 主应用组件
│   │   ├── App.css                   # 设计系统（赛博朋克暗色主题）
│   │   ├── index.css
│   │   ├── components/
│   │   │   ├── audio/                # AudioSourceSelector, AudioControls, AudioVisualizer
│   │   │   ├── subtitle/             # SubtitleList, SubtitleLine（diff 高亮 + TTS）
│   │   │   ├── settings/             # SettingsPanel, AsrSettings, ModelSettings, TtsSettings
│   │   │   ├── history/              # HistoryPanel（翻译历史浏览与搜索）
│   │   │   └── glossary/             # GlossaryManager（术语表 CRUD）
│   │   ├── hooks/                    # useWebSocket, useAudioCapture
│   │   ├── services/                 # WebSocketClient, AudioCaptureService, TtsClient
│   │   ├── stores/                   # Zustand: connection, subtitle, settings, tts
│   │   └── types/                    # TypeScript 类型定义（audio, config, ws-messages, electron）
│   └── README.md                     # 前端独立文档
│
├── models/                           # 本地 AI 模型（ASR / TTS / VAD）
│   ├── sherpa-onnx-paraformer/       # SenseVoice 多语言 ASR 模型（~230MB）
│   ├── sherpa-onnx-zipvoice-.../     # ZipVoice TTS 模型（~145MB）
│   ├── silero-vad/                   # Silero VAD 语音活动检测模型（~1MB）
│   └── vocos_24khz.onnx             # TTS 声码器（~52MB）
│
└── scripts/
    ├── download_model.py             # 下载 SenseVoice ASR 模型
    └── download_models.py            # 下载流式/离线 ASR + VAD 模型
```

### 核心数据流

```
麦克风 / 系统音频
       │
       ▼
  PCM 16kHz Mono ──WebSocket 二进制帧──▶ 后端 /ws/translate
                                              │
                                              ▼
                                    ASR 识别（本地 sherpa-onnx / 云端）
                                              │
                                              ▼
                                    句子累积器（SentenceAccumulator）
                                    检测句尾 → 发送 subtitle_draft
                                              │
                                              ▼
                                    LLM 翻译（OpenAI / Anthropic / DeepSeek）
                                              │
                                              ▼
                                    异步 LLM 校正（上下文 + 术语表）
                                    发送 subtitle_corrected（含 diff）
                                              │
                                              ▼
                                    前端实时显示：草稿 → 校正 → 最终字幕
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | React 19 + TypeScript 6 |
| 构建工具 | Vite 8 |
| 桌面壳 | Electron 41 |
| 状态管理 | Zustand 5（localStorage 持久化） |
| 图标库 | Lucide React |
| 后端框架 | Python FastAPI + Uvicorn |
| 数据库 | SQLAlchemy 2 (async) + aiosqlite (SQLite) |
| 本地 ASR | sherpa-onnx（SenseVoice / Zipformer / Paraformer） |
| 云端 ASR | 讯飞 RTASR/IAT、百度 |
| LLM 翻译 | OpenAI / Anthropic / DeepSeek / 自定义 OpenAI 兼容端点 |
| 本地 TTS | sherpa-onnx ZipVoice |
| 云端 TTS | Edge TTS、OpenAI TTS |
| 系统音频 | WASAPI Loopback (Windows) / sox (macOS) / PulseAudio (Linux) |
| 日志 | Loguru |
| 打包 | PyInstaller (后端) + electron-builder (前端) |

## 环境配置

### 前置要求

- **Node.js** >= 18
- **Python** >= 3.11
- **.NET 9 SDK**（仅 Windows 系统音频采集需要，用于编译 WASAPI 辅助程序）

### 1. 克隆项目

```bash
git clone <repository-url>
cd AI-translateAccessor
```

### 2. 后端环境配置

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

**Python 依赖清单（`requirements.txt`）：**

| 分类 | 包名 | 用途 |
|------|------|------|
| Web 框架 | fastapi, uvicorn, websockets | HTTP + WebSocket 服务 |
| 本地 ASR | sherpa-onnx | 语音识别推理引擎 |
| LLM 客户端 | openai | OpenAI / DeepSeek / 自定义端点调用 |
| 云端 TTS | edge-tts | Microsoft Edge TTS |
| 数据验证 | pydantic, pydantic-settings | 请求模型 + 环境变量配置 |
| 数据库 | sqlalchemy, aiosqlite | SQLite 异步 ORM |
| 音频处理 | numpy, soundfile | PCM 格式转换、重采样 |
| 日志 | loguru | 结构化日志 |
| 路径 | platformdirs | 跨平台用户数据目录 |
| 缓存 | redis | 可选，多 Worker 场景 |
| 配置 | python-dotenv | .env 文件加载 |

> **注意**：`anthropic` SDK 已在代码中支持但未在 `requirements.txt` 默认启用。如需使用 Anthropic Claude，执行 `pip install anthropic`。

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件。**开发时建议设置 `PORT=8000`**（默认 `0` 为系统自动分配，用于桌面打包）。

**核心配置（必须关注）：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `127.0.0.1` | 服务监听地址 |
| `PORT` | `0` | 服务端口（0 = 自动分配，开发建议 8000） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LLM_PROVIDER` | `openai` | LLM 提供商：`openai` / `anthropic` / `deepseek` |
| `LLM_MODEL` | `gpt-4o` | 模型名称 |
| `LLM_API_KEY` | （空） | API Key（必填，也可在前端 UI 设置） |
| `LLM_BASE_URL` | （空） | 自定义端点（如 Ollama: `http://localhost:11434/v1`） |
| `ENABLE_CORRECTION` | `true` | 是否启用 LLM 校正 |

**ASR / TTS 模型路径（通常留空，自动检测）：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODELS_DIR` | （空） | 模型根目录（默认 `models/`） |
| `ASR_MODEL_PATH` | （空） | ASR 模型路径（默认 `$MODELS_DIR/sherpa-onnx-paraformer`） |
| `ASR_ENCODER` | （空） | 流式 ASR 编码器路径 |
| `ASR_DECODER` | （空） | 流式 ASR 解码器路径 |
| `ASR_TOKENS` | （空） | ASR 词表文件路径 |
| `ASR_SAMPLE_RATE` | `16000` | ASR 采样率 |
| `ASR_FEATURE_DIM` | `80` | ASR 特征维度 |
| `TTS_MODEL_PATH` | （空） | TTS 模型路径（默认 `$MODELS_DIR/sherpa-onnx-zipvoice-...`） |
| `TTS_NUM_THREADS` | `2` | TTS 推理线程数 |

**音频参数（通常使用默认值）：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AUDIO_CHUNK_MS` | `200` | 音频分片时长（毫秒） |
| `AUDIO_BUFFER_SIZE` | `100` | 环形缓冲区容量（分片数） |
| `VAD_THRESHOLD` | `0.5` | VAD 语音检测阈值 |
| `MIN_SPEECH_DURATION` | `0.3` | 最短语音段时长（秒） |
| `MIN_SILENCE_DURATION` | `0.5` | 最短静音段时长（秒） |

**其他：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_DIR` | （空） | 数据目录（默认 `data/`，打包后为用户 AppData） |
| `CORS_ORIGINS` | `["*"]` | CORS 允许的来源 |
| `REDIS_URL` | （空） | Redis 地址（可选，多 Worker 场景） |
| `SESSION_TIMEOUT_SECONDS` | `3600` | 会话超时时间（秒） |
| `MAX_CONCURRENT_SESSIONS` | `50` | 最大并发会话数 |

**LLM 配置示例：**

| 提供商 | LLM_PROVIDER | LLM_MODEL | LLM_BASE_URL |
|--------|-------------|-----------|-------------|
| OpenAI | `openai` | `gpt-4o` / `gpt-4o-mini` | 留空 |
| Anthropic | `anthropic` | `claude-sonnet-4-20250514` | 留空 |
| DeepSeek | `deepseek` | `deepseek-chat` | `https://api.deepseek.com` |
| Ollama (本地) | `openai` | `qwen2.5:7b` | `http://localhost:11434/v1` |

可阅读官方接口文档

### 4. 下载 AI 模型

```bash
cd ..

# 下载 SenseVoice ASR 模型
python scripts/download_model.py

# 下载流式 ASR + VAD 模型
python scripts/download_models.py
```

模型默认下载到项目根目录的 `models/` 文件夹（约 430MB）。

### 5. 前端环境配置

```bash
cd frontend
npm install
```

### 6.（可选）编译 WASAPI 系统音频采集程序

仅 Windows 用户需要，用于捕获系统音频输出：

```bash
cd frontend/resources/wasapi-capture
dotnet publish -c Release -r win-x64 --self-contained
```

编译产物位于 `frontend/resources/wasapi-capture/bin/Release/net9.0/win-x64/publish/`。

## 服务启动

### 方式一：前后端分离启动（开发模式）

**启动后端：**

```bash
cd backend
venv\Scripts\activate    # Windows
# source venv/bin/activate  # macOS / Linux

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

后端启动成功后会输出 `AI_TRANSLATE_READY port=8000`。

**启动前端（浏览器模式）：**

```bash
cd frontend
npm run dev
```

浏览器访问 `http://localhost:5173`。

### 方式二：Electron 桌面应用启动（推荐）

```bash
cd frontend

# 开发模式（后端需单独启动）
npm run electron:dev

# 预览模式（先构建前端再启动 Electron，后端需单独启动）
npm run electron:preview
```

### 方式三：Docker 部署

```bash
cd backend

# 启动后端 + Redis
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

后端运行在 `http://localhost:8000`，Redis 运行在 `localhost:6379`。

## API 端点

### WebSocket

| 路径 | 说明 |
|------|------|
| `ws://127.0.0.1:{port}/ws/translate` | 实时翻译管道，客户端发送 PCM 音频 + JSON 控制消息，服务端返回字幕 JSON |

**控制消息类型：**
- `start` — 初始化会话（语言对、音频源、ASR/LLM 配置、术语表）
- `pause` / `resume` — 暂停 / 恢复翻译
- `stop` — 结束会话
- `update_glossary` — 运行时更新术语表
- `ping` — 心跳检测

### REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/tts` | 文本转语音 |
| GET | `/api/sessions` | 获取翻译会话列表 |
| POST | `/api/sessions` | 保存翻译会话 |
| GET | `/api/sessions/{id}/subtitles` | 获取会话字幕 |
| DELETE | `/api/sessions/{id}` | 删除会话 |
| GET | `/api/subtitles/search?q=...` | 全文搜索字幕 |
| POST | `/api/glossaries` | 创建术语表 |
| GET | `/api/glossaries` | 获取术语表列表 |
| GET | `/api/glossaries/{id}` | 获取术语表详情 |
| DELETE | `/api/glossaries/{id}` | 删除术语表 |

## 打包发布

### 一键打包（推荐）

```bash
# Windows（管理员权限运行）
build.bat

# macOS / Linux
chmod +x build.sh
./build.sh
```

脚本自动完成：PyInstaller 打包后端 → Vite 构建前端 → electron-builder 生成安装包。

产物在 `frontend/release/` 目录：
- **`AI 同声传译 Setup x.x.x.exe`** — NSIS 安装包（分发给用户）
- **`AI 同声传译 x.x.x.exe`** — 便携版（免安装）

### 手动打包

**第 1 步：打包 Python 后端**

```bash
cd backend
venv\Scripts\activate
pip install pyinstaller
pyinstaller ai-translate-backend.spec --noconfirm
```

产物：`backend/dist/ai-translate-backend.exe`

> 必须使用 `ai-translate-backend.spec`（含 hidden imports 和数据文件配置），而非简单的 `pyinstaller launcher.py`。

**第 2 步：构建 Electron 安装包**

```bash
cd frontend
npm install
npm run electron:build
```

electron-builder 会自动将以下内容打入安装包：
- 后端 `.exe` + Python 源码 + `.env`
- AI 模型（`models/`）
- WASAPI 系统音频采集程序

## 常见问题

**Q: ASR 模型加载失败？**
确认 `models/` 目录下存在模型文件，可通过 `scripts/download_model.py` 下载。

**Q: 系统音频采集无声音？**
Windows 用户需确保编译了 WASAPI 辅助程序（见环境配置第 6 步），并以管理员权限运行。

**Q: LLM 翻译超时？**
检查 `LLM_API_KEY` 和 `LLM_BASE_URL` 配置是否正确，网络是否可达。

**Q: electron-builder 下载 Electron 超时？**
设置国内镜像：`set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/`

**Q: electron-builder 提示符号链接权限不足？**
以管理员身份运行 `build.bat`，或开启 Windows 开发者模式。

## 许可证

本项目仅供学习和个人使用。
