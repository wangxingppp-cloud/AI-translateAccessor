# AI 同声传译助手

AI 同声传译助手 — 实时语音识别、翻译与字幕显示桌面应用。帮助用户在观看外语音视频、参加线上会议时获得实时翻译字幕。

## 功能特性

- **实时语音识别** — 支持本地离线 ASR（sherpa-onnx SenseVoice / Zipformer / Paraformer）和云端 ASR（讯飞 RTASR、讯飞 IAT、百度）
- **LLM 翻译与校正** — 支持 OpenAI、Anthropic、DeepSeek 及任意 OpenAI 兼容端点（Ollama、vLLM 等），异步校正翻译结果并展示 diff 高亮
- **本地 NMT 翻译** — 基于 Helsinki-NLP/opus-mt-en-zh 的 ONNX 量化模型，无需 API 调用即可本地翻译（~100-300ms）
- **系统音频采集** — Windows 下通过 WASAPI Loopback 捕获系统音频，无需虚拟声卡
- **文本转语音** — 支持本地离线 TTS（sherpa-onnx ZipVoice）、Edge TTS、OpenAI TTS
- **术语表管理** — 自定义领域术语，LLM 校正时自动注入保持翻译一致性
- **翻译历史** — SQLite 持久化所有会话与字幕记录，支持全文搜索
- **桌面应用** — Electron 桌面壳，无边框窗口，置顶显示，支持 Windows / macOS / Linux

## 项目架构

```
AI-translateAccessor/
├── build.bat                         # Windows 一键打包脚本
├── build.sh                          # macOS/Linux 一键打包脚本
│
├── backend/                          # Python FastAPI 后端
│   ├── launcher.py                   # PyInstaller 打包入口
│   ├── ai-translate-backend.spec     # PyInstaller 打包配置
│   ├── requirements.txt              # Python 依赖
│   ├── Dockerfile                    # Docker 镜像构建文件
│   ├── docker-compose.yml            # Docker 部署配置（后端 + Redis）
│   ├── .env.example                  # 环境变量模板
│   ├── app/
│   │   ├── main.py                   # FastAPI 应用工厂 + uvicorn 启动入口
│   │   ├── config.py                 # Pydantic Settings 配置中心
│   │   ├── api/
│   │   │   ├── ws.py                 # WebSocket /ws/translate 实时翻译管道
│   │   │   └── rest.py               # REST API（健康检查、TTS、历史、术语表）
│   │   ├── core/
│   │   │   ├── session_manager.py    # 会话状态机
│   │   │   ├── connection_manager.py # WebSocket 连接管理
│   │   │   └── audio_buffer.py       # 音频环形缓冲区
│   │   ├── engines/
│   │   │   ├── asr/
│   │   │   │   ├── sherpa_engine.py       # 本地 ASR 引擎
│   │   │   │   ├── cloud_asr.py           # 云端 ASR（讯飞/百度）
│   │   │   │   ├── audio_capture.py       # Windows WASAPI 系统音频采集
│   │   │   │   ├── ring_buffer.py         # 30 秒环形缓冲区
│   │   │   │   ├── mark_processor.py      # VAD 标记生成器
│   │   │   │   ├── transcription_worker.py# 后台转录工作线程
│   │   │   │   ├── stream_handler.py      # 流式 ASR 句子边界检测
│   │   │   │   └── vad_processor.py       # 语音活动检测
│   │   │   ├── correction/
│   │   │   │   └── corrector.py           # LLM 翻译校正引擎
│   │   │   ├── translation/
│   │   │   │   ├── context_manager.py     # 滑动窗口翻译上下文
│   │   │   │   └── nmt_engine.py          # 本地 NMT 翻译（ONNX opus-mt-en-zh）
│   │   │   └── tts/
│   │   │       └── tts_engine.py          # 离线 TTS（sherpa-onnx ZipVoice）
│   │   ├── db/
│   │   │   ├── database.py           # SQLAlchemy async SQLite
│   │   │   ├── models.py             # ORM 模型
│   │   │   └── repositories/         # 数据仓库（预留）
│   │   ├── models/                   # Pydantic 数据模型
│   │   │   ├── subtitle.py
│   │   │   ├── session.py
│   │   │   └── glossary.py
│   │   ├── services/
│   │   │   ├── history_service.py    # 翻译历史 CRUD
│   │   │   └── glossary_service.py   # 术语表 CRUD
│   │   └── utils/
│   │       ├── logger.py             # Loguru 日志配置
│   │       └── metrics.py            # 管道延迟指标
│   ├── models/                       # 本地 AI 模型（NMT 等）
│   └── tests/                        # 测试包
│
├── frontend/                         # React + Electron 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
│   ├── eslint.config.js
│   ├── electron/
│   │   ├── main.ts                   # Electron 主进程
│   │   ├── preload.cjs               # Context Bridge
│   │   ├── backend.ts                # 后端进程管理
│   │   ├── ipc/
│   │   │   └── audio.ts              # 音频 IPC 通道
│   │   └── audio/
│   │       ├── types.ts              # SystemAudioCapturer 接口
│   │       ├── windows.ts            # Windows WASAPI
│   │       ├── macos.ts              # macOS sox/BlackHole
│   │       └── linux.ts              # Linux PulseAudio/PipeWire
│   ├── resources/
│   │   ├── wasapi-capture/           # WASAPI 辅助程序源码
│   │   └── wasapi-capture-bin/       # WASAPI 辅助程序编译产物
│   └── src/
│       ├── main.tsx                  # React 入口
│       ├── App.tsx                   # 主应用组件
│       ├── App.css                   # 样式
│       ├── components/
│       │   ├── audio/                # AudioSourceSelector, AudioControls, AudioVisualizer
│       │   ├── subtitle/             # SubtitleList, SubtitleLine
│       │   ├── settings/             # SettingsPanel, AsrSettings, ModelSettings, TtsSettings
│       │   ├── history/              # HistoryPanel
│       │   └── glossary/             # GlossaryManager
│       ├── hooks/                    # useWebSocket, useAudioCapture
│       ├── services/                 # WebSocketClient, AudioCaptureService, TtsClient
│       ├── stores/                   # Zustand: connection, subtitle, settings, tts
│       └── types/                    # TypeScript 类型定义
│
├── models/                           # 本地 AI 模型（ASR / TTS / VAD）
├── scripts/                          # 模型下载脚本
└── data/                             # 运行时数据（SQLite 等）
```

### 核心数据流

```
麦克风 / 系统音频
       │
       ▼
  PCM 16kHz Mono ──WebSocket──▶ 后端 /ws/translate
                                    │
                                    ▼
                          ASR 识别（本地 / 云端）
                                    │
                                    ▼
                          句子累积器 → subtitle_draft
                                    │
                                    ▼
                          LLM 翻译 / 本地 NMT 翻译
                                    │
                                    ▼
                          异步 LLM 校正 → subtitle_corrected
                                    │
                                    ▼
                          前端实时显示字幕
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19 + TypeScript 6 + Vite 8 + Electron 41 + Zustand 5 |
| 后端 | Python FastAPI + Uvicorn + SQLAlchemy 2 (async SQLite) |
| 本地 ASR | sherpa-onnx（SenseVoice / Zipformer / Paraformer） |
| 云端 ASR | 讯飞 RTASR/IAT、百度 |
| 本地 NMT | ONNX Runtime + Helsinki-NLP/opus-mt-en-zh（INT8 量化） |
| LLM 翻译 | OpenAI / Anthropic / DeepSeek / 自定义端点 |
| 本地 TTS | sherpa-onnx ZipVoice |
| 云端 TTS | Edge TTS、OpenAI TTS |
| 系统音频 | WASAPI Loopback (Windows) / sox (macOS) / PulseAudio (Linux) |

## 环境配置

### 前置要求

- **Node.js** >= 18
- **Python** >= 3.11
- **.NET 9 SDK**（仅 Windows 系统音频采集需要）

### 1. 克隆项目

```bash
git clone <repository-url>
cd AI-translateAccessor
```

### 2. 后端环境配置

```bash
cd backend

# 创建并激活虚拟环境
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

**Python 依赖清单：**

| 分类 | 包名 | 用途 |
|------|------|------|
| Web | fastapi, uvicorn, websockets | HTTP + WebSocket 服务 |
| 本地 ASR | sherpa-onnx | 语音识别 |
| 本地 NMT | onnxruntime, transformers, sentencepiece | 本地翻译（opus-mt-en-zh） |
| LLM | openai | OpenAI / DeepSeek / 自定义端点 |
| TTS | edge-tts | Microsoft Edge TTS |
| 数据 | pydantic, pydantic-settings, sqlalchemy, aiosqlite | 验证 + ORM |
| 音频 | numpy, soundfile | PCM 处理 |
| 工具 | loguru, platformdirs, python-dotenv, redis | 日志 + 路径 + 配置 |

> **注意**：`anthropic` SDK 已在代码中支持但未默认安装。如需使用，执行 `pip install anthropic`。

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件。**开发时建议 `PORT=8000`**。

**核心配置：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `127.0.0.1` | 监听地址 |
| `PORT` | `0` | 端口（0 = 自动分配，开发建议 8000） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LLM_PROVIDER` | `openai` | `openai` / `anthropic` / `deepseek` |
| `LLM_MODEL` | `gpt-4o` | 模型名称 |
| `LLM_API_KEY` | （空） | API Key（也可在前端 UI 设置） |
| `LLM_BASE_URL` | （空） | 自定义端点（如 Ollama: `http://localhost:11434/v1`） |
| `ENABLE_CORRECTION` | `true` | 启用 LLM 校正 |

**模型路径（通常留空自动检测）：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODELS_DIR` | （空） | 模型根目录 |
| `ASR_MODEL_PATH` | （空） | ASR 模型路径 |
| `ASR_ENCODER` / `ASR_DECODER` / `ASR_TOKENS` | （空） | 流式 ASR 模型文件路径 |
| `TTS_MODEL_PATH` | （空） | TTS 模型路径 |

**高级参数（通常使用默认值）：**

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_DIR` | （空） | 数据目录（默认 `data/`） |
| `ASR_SAMPLE_RATE` | `16000` | ASR 采样率 |
| `TTS_NUM_THREADS` | `2` | TTS 推理线程数 |
| `AUDIO_CHUNK_MS` | `200` | 音频分片时长（ms） |
| `VAD_THRESHOLD` | `0.5` | VAD 检测阈值 |
| `CORS_ORIGINS` | `["*"]` | CORS 来源 |
| `REDIS_URL` | （空） | Redis 地址（可选） |
| `SESSION_TIMEOUT_SECONDS` | `3600` | 会话超时 |
| `MAX_CONCURRENT_SESSIONS` | `50` | 最大并发会话 |

**LLM 配置示例：**

| 提供商 | LLM_PROVIDER | LLM_MODEL | LLM_BASE_URL |
|--------|-------------|-----------|-------------|
| OpenAI | `openai` | `gpt-4o` / `gpt-4o-mini` | 留空 |
| Anthropic | `anthropic` | `claude-sonnet-4-20250514` | 留空 |
| DeepSeek | `deepseek` | `deepseek-chat` | `https://api.deepseek.com` |
| Ollama | `openai` | `qwen2.5:7b` | `http://localhost:11434/v1` |

### 4. 下载 AI 模型

```bash
cd ..

# 下载 SenseVoice ASR 模型
python scripts/download_model.py

# 下载流式 ASR + VAD 模型
python scripts/download_models.py
```

模型下载到项目根目录的 `models/` 文件夹。

### 5. 前端环境配置

```bash
cd frontend
npm install
```

### 6.（可选）编译 WASAPI 系统音频采集程序

仅 Windows 用户需要：

```bash
cd frontend/resources/wasapi-capture
dotnet publish -c Release -r win-x64 --self-contained
```

> 已有编译产物在 `wasapi-capture-bin/` 目录，如无需重新编译可跳过。

## 服务启动

### 方式一：前后端分离启动（开发模式）

**启动后端：**

```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动成功输出 `AI_TRANSLATE_READY port=8000`。

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

# 预览模式（后端需单独启动）
npm run electron:preview
```

### 方式三：Docker 部署

```bash
cd backend
docker-compose up -d
```

后端 `http://localhost:8000`，Redis `localhost:6379`。

## API 端点

### WebSocket

| 路径 | 说明 |
|------|------|
| `ws://127.0.0.1:{port}/ws/translate` | 实时翻译管道 |

控制消息：`start`、`pause`、`resume`、`stop`、`update_glossary`、`ping`

### REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/tts` | 文本转语音 |
| GET | `/api/sessions` | 会话列表 |
| POST | `/api/sessions` | 保存会话 |
| GET | `/api/sessions/{id}/subtitles` | 会话字幕 |
| DELETE | `/api/sessions/{id}` | 删除会话 |
| GET | `/api/subtitles/search?q=...` | 搜索字幕 |
| POST | `/api/glossaries` | 创建术语表 |
| GET | `/api/glossaries` | 术语表列表 |
| GET | `/api/glossaries/{id}` | 术语表详情 |
| DELETE | `/api/glossaries/{id}` | 删除术语表 |

## 打包发布

### 一键打包（推荐）

```bash
# Windows（管理员权限）
build.bat

# macOS / Linux
chmod +x build.sh
./build.sh
```

产物在 `frontend/release/`：
- **`AI 同声传译 Setup x.x.x.exe`** — 安装包（分发给用户）
- **`AI 同声传译 x.x.x.exe`** — 便携版（免安装）

### 手动打包

```bash
# 第 1 步：打包后端
cd backend
pyinstaller ai-translate-backend.spec --noconfirm

# 第 2 步：打包前端
cd ../frontend
npm run electron:build
```

> 必须使用 `ai-translate-backend.spec`，其中包含 hidden imports 和数据文件配置。

## 常见问题

**Q: ASR 模型加载失败？**
确认 `models/` 目录下存在模型文件，执行 `scripts/download_model.py` 下载。

**Q: 系统音频采集无声音？**
确保编译了 WASAPI 辅助程序（见第 6 步），并以管理员权限运行。

**Q: LLM 翻译超时？**
检查 `LLM_API_KEY` 和 `LLM_BASE_URL` 是否正确，网络是否可达。

**Q: electron-builder 下载超时？**
设置镜像：`set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/`

**Q: 符号链接权限不足？**
管理员运行 `build.bat`，或开启 Windows 开发者模式。

## 许可证

本项目仅供学习和个人使用。
