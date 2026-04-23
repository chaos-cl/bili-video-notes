# Bilibili Notes — 分发说明

> 版本: 0.1.0 | 更新: 2026-04-23

将 Bilibili 视频自动转换为结构化 Obsidian Markdown 笔记。输入视频链接或UP主名称，自动完成数据获取、关键帧抽取、语音转录、画面识别，生成 Markdown 笔记保存到 Obsidian。

## 一键安装

```bash
# 克隆或解压后进入目录
bash install.sh
```

安装脚本自动检查并安装：Python 依赖、ffmpeg、yt-dlp、bilibili-cli。

安装后需要手动完成两步：
1. `bili auth login` — 扫码登录B站账号
2. `export MINIMAX_API_KEY="your-key"` — 设置 MiniMax API 密钥

## 使用

```bash
uv run python scripts/pipeline.py --bv BV1ABcsztEcY
uv run python scripts/pipeline.py --url "https://www.bilibili.com/video/BV1ABcsztEcY"
uv run python scripts/pipeline.py --url "https://b23.tv/xxxxx"
uv run python scripts/pipeline.py --user "影视飓风" --max 10
```

## AI 推理模型

### 云端推理（默认）

| 项目 | 说明 |
|------|------|
| 服务商 | MiniMax |
| 模型 | MiniMax-M2.7 |
| API 格式 | Anthropic 兼容 |
| 配置方式 | 环境变量 `MINIMAX_API_KEY` |
| 优势 | 无需本地 GPU，跨平台，输出质量高 |
| 费用 | 按用量计费 |

### 本地推理（可选）

| 项目 | 说明 |
|------|------|
| 服务 | oMLX |
| LLM | Qwen3.6-35B-A3B-nvfp4（笔记生成） |
| VLM | Qwen3-VL-8B-Instruct-MLX-4bit（帧分析） |
| 硬件要求 | Apple Silicon Mac (M1/M2/M3/M4) |
| 优势 | 完全离线、免费、无速率限制 |
| 语音转录 | mlx-whisper（本地 Apple Silicon GPU 加速） |

### 切换方式

编辑 `config.yaml` 中 `provider` 字段：

```yaml
# 云端推理（默认）
provider: "minimax"

# 本地推理（需要 oMLX 服务运行中）
# provider: "omlx"
```

或通过命令行参数临时切换：

```bash
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --provider minimax
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --provider omlx
```

### 本地推理环境配置

如需使用本地推理，取消 `config.yaml` 中 omlx 配置的注释，并确保：
1. oMLX 服务已启动，监听 `localhost:8000`
2. LLM 和 VLM 模型已加载
3. 验证：`curl http://localhost:8000/v1/models`

语音转录（可选，仅 Apple Silicon）：
```bash
uv sync --extra whisper
```

## 系统要求

| 依赖 | 版本 | 必需 | 用途 |
|------|------|------|------|
| Python | >= 3.12 | 是 | 运行环境 |
| uv | latest | 是 | 包管理 |
| bilibili-cli | >= 0.6.2 | 是 | B站数据（需登录） |
| ffmpeg | any | 是 | 关键帧抽取 |
| yt-dlp | >= 2026.3 | 是 | 视频下载 |
| MiniMax API Key | — | 二选一 | 云端推理 |
| oMLX 服务 | — | 二选一 | 本地推理 |
| mlx-whisper | — | 可选 | 本地语音转录 |

## 输出

```
Obsidian Vault/
├── video-notes/
│   └── 标题(BV号).md        # 结构化笔记
└── video-notes-images/
    └── BV号/
        └── frame_NNN.png    # 关键帧图片
```

笔记内容包含：YAML frontmatter、概要、关键帧（图片+描述）、详细笔记、精选评论、标签。

## AI 智能体集成

本项目包含三个入口文件，兼容主流 AI 编码工具：

| 文件 | 平台 | 说明 |
|------|------|------|
| `CLAUDE.md` | Claude Code | 项目上下文和快捷命令 |
| `AGENTS.md` | OpenClaw / Hermes | 通用入口，含完整环境配置步骤 |
| `SKILL.md` | Claude Code (Skill) | 技能定义，支持触发词调用 |

智能体克隆仓库后读取 `AGENTS.md` 即可自动配置环境并使用。

## 故障排查

| 问题 | 解决 |
|------|------|
| bili 未认证 | `bili auth login` 扫码登录 |
| MINIMAX_API_KEY 未设置 | `export MINIMAX_API_KEY="..."` 或用 `--provider omlx` |
| oMLX 连接失败 | 启动 oMLX 或用 `--provider minimax` |
| yt-dlp cookies 错误 | 检查浏览器登录状态 |
| 笔记标题为 BV号 | bili 数据获取被限流，等待后用 `--force` 重试 |

## 项目结构

```
bilibili-notes/
├── install.sh            # 一键安装脚本
├── config.yaml           # 运行时配置
├── pyproject.toml         # Python 依赖
├── SKILL.md               # Claude Code 技能定义
├── CLAUDE.md              # Claude Code 项目上下文
├── AGENTS.md              # OpenClaw/Hermes 通用入口
├── scripts/
│   ├── common.py          # 配置、日志、API 客户端
│   ├── fetch_data.py      # bili CLI 数据获取
│   ├── extract_frames.py  # yt-dlp + ffmpeg 关键帧
│   ├── transcribe_audio.py# mlx-whisper 语音转录
│   ├── analyze_frames.py  # VLM 帧分析
│   ├── generate_notes.py  # LLM 笔记生成
│   └── pipeline.py        # 流水线入口
└── templates/
    └── note_template.md   # 笔记模板
```

## License

MIT
