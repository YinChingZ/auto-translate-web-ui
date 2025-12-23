# AutoTranslateWebUI

一个本地/自托管的「视频自动转录 + 自动翻译 + 可视化字幕精修」Web 应用。

核心流程：上传视频 → 提取音频 → VAD 分段 → Whisper 转写 → LLM 翻译 → 在线编辑字幕 → 导出 SRT。

## 功能概览

- 视频上传并异步处理（Celery worker 后台跑长任务）
- 自动语音分段（Silero VAD），只对有语音的片段做识别，减少静音“幻觉”
- Whisper 转写（自动选择 CPU/CUDA；可在上传时指定模型大小）
- LLM 逐句翻译（带上下文窗口；编辑原文可触发“重翻译”）
- 字幕编辑器：
	- 编辑原文/译文、调整起止时间
	- 新增/删除字幕
	- 一键重翻译单条字幕（带相邻上下文 + 已翻译上下文）
	- 导出原文/译文 SRT

## 技术栈

- 后端：FastAPI + SQLAlchemy(Async) + SQLite（默认）
- 异步任务：Celery + Redis（broker/backend）
- 音频/识别：ffmpeg + silero-vad + openai-whisper
- 翻译：OpenAI SDK（可配置 base_url / model）
- 前端：React + Vite + Tailwind + Zustand

## 仓库结构

```
backend/         FastAPI + Celery + pipeline
	api/routes.py  API 路由（上传/状态/字幕 CRUD/导出）
	services/      处理流水线（提取音频、VAD、Whisper、翻译）
	tasks.py       Celery 任务入口
	config.py      配置（.env / 环境变量）
frontend/        React + Vite Web UI
uploads/         上传视频与临时音频（默认 gitignore）
.vscode/         VS Code 任务（Windows 友好）
```

## API 概览

- `POST /api/videos/upload`：上传视频并启动处理
	- `multipart/form-data`：
		- `file`：视频文件
		- `batch_size`：翻译批次大小（当前实现为逐句翻译，字段用于记录/兼容）
		- `context_window`：上下文窗口（用于逐句翻译上下文）
		- `whisper_model`：Whisper 模型名（tiny/base/small/medium/large）
- `GET /api/videos/{video_id}/status`：轮询任务状态，返回 `video_url`
- `GET /api/videos/{video_id}/subtitles`：获取字幕列表
- `PUT /api/subtitles/{sub_id}?trigger_translation=true|false`：更新字幕（可触发重翻译）
- `POST /api/videos/{video_id}/subtitles`：新增字幕
- `DELETE /api/subtitles/{sub_id}`：删除字幕
- `GET /api/videos/{video_id}/export?translated=true|false`：导出 SRT

后端自带 Swagger：`http://localhost:8000/docs`

## Windows 运行指南（开发环境）

> 本项目的 VS Code Tasks 已为 Windows 配好（`.vscode/tasks.json`）。如果你使用 VS Code，推荐直接用任务启动。

### 0) 前置依赖

1. **Git**
2. **Python 3.10+**（建议 3.11）
3. **Node.js 18+**（建议 LTS）
4. **Redis**（Celery 需要）
5. **FFmpeg**（音频提取需要，必须在 PATH 中可用）

#### FFmpeg 安装（任选其一）

- `winget install Gyan.FFmpeg`
- 或 `choco install ffmpeg`

验证：`ffmpeg -version`

#### Redis 启动（推荐 Docker；二选一）

- **方案 A：Docker（推荐）**
	- `docker run --name autotranslate-redis -p 6379:6379 -d redis:7-alpine`
- **方案 B：本机安装 Redis**
	- 任意方式安装后，确保 `redis://localhost:6379/0` 可连通

### 1) 后端安装

在仓库根目录打开 PowerShell：

```powershell
py -m venv backend\venv
backend\venv\Scripts\python -m pip install -U pip
backend\venv\Scripts\pip install -r backend\requirements.txt
```

> 说明：流水线里会用到 `torch`（silero-vad/whisper 依赖）。如果你的环境里没有自动装上 torch，按需手动安装：
>
> ```powershell
> backend\venv\Scripts\pip install torch
> ```

### 2) 配置环境变量（必做）

创建文件：`backend/.env`（不会被提交，已在 `.gitignore` 中忽略）

最小配置示例：

```env
OPENAI_API_KEY=你的key

# 可选：自定义 OpenAI 兼容网关
OPENAI_BASE_URL=https://api.openai.com/v1

# 可选：模型
OPENAI_MODEL=gpt-4o-mini

# 可选：默认 Whisper 模型（也可在上传时覆盖）
WHISPER_MODEL=medium

# 可选：翻译目标语言
TARGET_LANGUAGE=Chinese

# 可选：SQLite（默认会在仓库根目录生成 app.db）
DATABASE_URL=sqlite+aiosqlite:///./app.db

# 必须：Redis
REDIS_URL=redis://localhost:6379/0

# 可选：调试
DEBUG=false
```

### 3) 前端安装

```powershell
Set-Location frontend
npm install
```

### 4) 启动（推荐 VS Code Tasks）

VS Code：`Terminal -> Run Task...`，依次启动：

- `Run Backend`
- `Run Celery Worker`
- `Run Frontend`

启动后访问：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`（Swagger：`/docs`）

> Vite 已配置代理：`/api` 与 `/uploads` 会转发到 `http://localhost:8000`。

### 5) 不用 VS Code Tasks 的手动启动方式

在仓库根目录开 3 个 PowerShell 窗口：

1) 后端 API

```powershell
backend\venv\Scripts\uvicorn backend.main:app --reload --reload-dir backend
```

2) Celery Worker（Windows 下已用 `-P solo`）

```powershell
backend\venv\Scripts\celery -A backend.tasks.celery_app worker --loglevel=info -P solo
```

3) 前端

```powershell
Set-Location frontend
npm run dev
```

## 使用说明

1. 打开前端页面上传视频（支持 `.mp4/.mkv/.avi/.mov/.webm` 等）
2. 上传时可选择：
	 - Whisper 模型（影响速度/准确率）
	 - Context Window（翻译时参考的前后句数量）
3. 上传后前端会轮询状态；完成后进入编辑器
4. 编辑器支持：
	 - 点击字幕跳转并播放
	 - 改原文后自动重翻译（如果开启触发）
	 - 导出原文/译文 SRT

## 常见问题（Windows）

- **Celery 连接不上 Redis**：确认 Redis 运行中，且 `REDIS_URL` 正确（默认 `redis://localhost:6379/0`）。
- **`ffmpeg` 找不到**：确保已安装并加入 PATH，PowerShell 执行 `ffmpeg -version` 能输出版本。
- **Whisper 太慢**：使用更小的 `whisper_model`（如 `base`/`small`），或配置 GPU 环境。
- **CUDA 不生效**：需要正确安装带 CUDA 的 `torch`，并确保显卡驱动与 CUDA 版本匹配；否则会自动回退到 CPU。
- **app.db 在哪**：默认 `DATABASE_URL=sqlite+aiosqlite:///./app.db`，通常会在“仓库根目录”生成 `app.db`。

## 设计/实现要点（简述）

- 后端把 `uploads/` 挂载为静态目录：浏览器可用 `/uploads/<filename>` 访问视频
- 上传接口会把 `batch_size/context_window/whisper_model` 写入 `videos.config`，Celery 任务读取并用于 pipeline
- `PUT /api/subtitles/{id}` 支持 `trigger_translation=true`：按当前字幕前后上下文重翻译并更新译文
