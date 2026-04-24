# Bilibili Notes

将 Bilibili 视频自动转换为结构化 Obsidian Markdown 笔记的命令行工具。

输入一个视频链接或UP主名称，自动完成数据获取、关键帧抽取、语音转录、画面识别，最终生成一份包含概要、关键帧、详细笔记和精选评论的 Markdown 文件，保存到 Obsidian vault。

## 功能

- **多格式输入** — 支持 BV号、视频 URL、b23.tv 短链、UP主名/UID，按输入模式严格解析
- **批量处理** — 指定UP主即可批量生成其最新视频的笔记
- **双 LLM 引擎** — 本地 oMLX（免费、离线）或云端 MiniMax（高质量）
- **智能转录** — 有字幕直接用字幕，无字幕时才下载音频用 mlx-whisper 本地转录
- **关键帧抽取** — ffmpeg 场景变化检测，自动回退等间隔采样，重跑时自动清理旧帧
- **帧画面理解** — VLM 逐帧分析生成中文描述（需 omlx 等支持视觉的 OpenAI 兼容接口；minimax 为纯文本模型自动跳过）
- **Obsidian 联动** — 笔记和图片直接保存到 Obsidian vault，图片用相对路径引用，路径安全校验
- **健壮设计** — 数据获取硬失败、YAML frontmatter 安全生成、CLI 参数正确穿透、中间产物可控清理

## 快速开始

### 1. 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | >= 3.12 | 运行环境 |
| uv | latest | Python 包管理 |
| bilibili-cli | >= 0.6.2 | B站数据获取（需登录认证） |
| ffmpeg | any | 视频处理和关键帧抽取 |
| yt-dlp | >= 2026.3 | 视频下载 |

**本地推理（可选）：**
- oMLX 服务运行在 `localhost:8000`，加载 VLM + LLM 模型
- mlx-whisper 用于本地语音转录（延迟加载，仅在使用时才需要）

**云端推理（可选）：**
- MiniMax API（Anthropic 兼容格式），环境变量 `MINIMAX_API_KEY`

### 2. 安装

```bash
# 一键安装（推荐）
bash install.sh

# 或手动安装
git clone https://github.com/chaos-cl/bili-video-notes.git
cd bili-video-notes
uv sync

# 安装语音转录依赖（仅 Apple Silicon macOS，可选）
uv sync --extra whisper

# 安装开发依赖
uv sync --extra dev

# 验证 bilibili-cli 已安装并认证
bili status

# 验证 ffmpeg
ffmpeg -version
```

### 3. 配置

编辑 `config.yaml`：

```yaml
# 本地 oMLX 推理服务
omlx:
  base_url: "http://localhost:8000/v1"
  api_key_env: "OMLX_API_KEY"                    # 从环境变量读取密钥
  llm_model: "Qwen3.6-35B-A3B-nvfp4"            # 文本生成模型
  vlm_model: "Qwen3-VL-8B-Instruct-MLX-4bit"    # 视觉理解模型

# 云端 MiniMax 推理服务（Anthropic 兼容 API）
minimax:
  base_url: "https://api.minimaxi.com/anthropic"
  api_key_env: "MINIMAX_API_KEY"    # 从环境变量读取密钥
  model: "MiniMax-M2.7"

# 默认使用的推理服务: omlx 或 minimax
provider: "minimax"

# Obsidian vault 配置
obsidian:
  vault_path: "~/Documents/Bilibili/Bilibili"  # vault 根目录
  notes_dir: "video-notes"                     # 笔记子目录
  images_dir: "video-notes-images"             # 图片子目录

# 关键帧抽取参数
frames:
  scene_threshold: 0.3    # 场景变化阈值（越小越敏感，抽帧越多）
  min_interval: 30        # 最小帧间隔（秒）
  max_frames: 20          # 最大帧数
  max_width: 1920         # 图片最大宽度（像素）

# Whisper 语音转录参数
whisper:
  model: "large-v3-turbo"  # 模型名称
  language: "auto"         # auto 为自动检测
  device: "mlx"            # mlx 为 Apple Silicon 加速

# 日志配置
logging:
  dir: "logs"
  level: "INFO"
```

### 4. 使用

```bash
# 单个视频（BV号）
uv run python scripts/pipeline.py --bv BV1ABcsztEcY

# 单个视频（URL）
uv run python scripts/pipeline.py --url "https://www.bilibili.com/video/BV1ABcsztEcY"

# 短链
uv run python scripts/pipeline.py --url "https://b23.tv/xxxxx"

# 批量处理 UP 主的最近 10 个视频
uv run python scripts/pipeline.py --user "影视飓风"

# 指定 UP 主 UID 和最大视频数
uv run python scripts/pipeline.py --user 946974 --max 50

# 使用云端 MiniMax 生成（需要 MINIMAX_API_KEY）
export MINIMAX_API_KEY="your-key-here"
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --provider minimax

# 强制重新生成（覆盖已有笔记并清理旧帧）
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --force

# 覆盖 vault 路径
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --vault /path/to/vault

# 使用自定义配置文件
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --config /path/to/config.yaml
```

## 输出结构

```
Obsidian Vault/
├── video-notes/
│   ├── 能卖上亿美金？国产短剧如何征服世界？(BV1ABcsztEcY).md
│   └── ...
└── video-notes-images/
    ├── BV1ABcsztEcY/
    │   ├── frame_001.png
    │   ├── frame_002.png
    │   └── ...
    └── ...
```

生成的笔记格式：

```markdown
---
title: 视频标题
bvid: BV1xxxxx
author: UP主名
duration: "11:19"
url: https://www.bilibili.com/video/BV1xxxxx
date: 2026-04-23
tags:
- bilibili
---

# 视频标题
> 来源: [BV1xxxxx](url) | UP主: xxx | 时长: 11:19

## 概要
2-3句话的视频概要

## 关键帧
![frame_001.png](../video-notes-images/BV1xxxxx/frame_001.png)
> 关键帧描述

## 详细笔记
结构化的详细笔记内容

## 精选评论
代表性评论摘要

## 标签
#bilibili #标签1 #标签2
```

## 项目结构

```
bilibili-notes/
├── config.yaml              # 运行时配置（密钥从环境变量读取）
├── pyproject.toml            # 项目依赖 + 构建系统
├── install.sh                # 一键安装脚本
├── SKILL.md                  # AI 工具入口定义
├── scripts/
│   ├── common.py             # 共享工具：配置校验、日志、API 客户端、重试、路径安全
│   ├── fetch_data.py         # bili CLI 数据获取：视频信息、字幕、评论、延迟音频下载
│   ├── extract_frames.py     # yt-dlp 下载 + ffmpeg 关键帧抽取（清理旧帧 + 返回码检查）
│   ├── transcribe_audio.py   # mlx-whisper 本地语音转录（延迟导入）
│   ├── analyze_frames.py     # VLM 逐帧视觉识别（仅 OpenAI 兼容接口支持图片输入）
│   ├── generate_notes.py     # LLM 融合所有信息生成 Markdown（安全 YAML + 长度截断）
│   └── pipeline.py           # 流水线编排 + CLI 入口（参数穿透 + 硬失败 + force 清理）
├── templates/
│   └── note_template.md      # 笔记模板
├── tests/                    # 单元测试
├── work/                     # 运行时临时文件（转录结果等）
└── logs/                     # 运行日志
```

## AI 智能体集成指南

本项目的 `SKILL.md` 定义了 AI 工具入口，可被 Claude Code、OpenClaw、Hermes 等智能体识别和调用。

### 环境配置步骤（供 AI 智能体参考）

```bash
# 1. 确认 Python 3.12+
python3 --version

# 2. 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh && sh /tmp/uv-install.sh

# 3. 克隆并安装依赖
git clone https://github.com/chaos-cl/bili-video-notes.git && cd bili-video-notes
uv sync
uv sync --extra dev  # 开发环境

# 4. 安装 bilibili-cli（如未安装）
# 参考: https://github.com/public-clis/bilibili-cli
# macOS:
brew install bilibili-cli
bili auth login  # 需要扫码登录 B站账号

# 5. 安装 ffmpeg（如未安装）
brew install ffmpeg

# 6. 安装 yt-dlp（如未安装）
brew install yt-dlp

# 7. 配置 config.yaml
# 复制示例配置并修改 vault_path 等参数
cp config.yaml.example config.yaml
# 编辑 config.yaml 设置你的 Obsidian vault 路径

# 8. 设置 API 密钥（根据选择的 provider）
# MiniMax 云端推理
export MINIMAX_API_KEY="your-api-key"
# 或 oMLX 本地推理
export OMLX_API_KEY="your-key"  # 本地服务通常为空即可

# 9. 验证环境
bili status                    # bilibili-cli 认证状态
ffmpeg -version                # ffmpeg 可用
yt-dlp --version               # yt-dlp 可用
curl localhost:8000/v1/models  # oMLX 服务（如使用本地推理）

# 10. 生成第一个笔记
uv run python scripts/pipeline.py --bv BV1ABcsztEcY
```

### 调用方式

**CLI 直接调用：**
```bash
uv run python scripts/pipeline.py --bv <BV号>
uv run python scripts/pipeline.py --url <视频URL>
uv run python scripts/pipeline.py --user <UP主名或UID> --max <数量>
uv run python scripts/pipeline.py --bv <BV号> --config <配置文件> --vault <vault路径>
```

**Python 代码调用：**
```python
from scripts.pipeline import run_pipeline
from scripts.common import load_config

# 处理单个视频
config = load_config()  # 支持自定义配置路径: load_config("path/to/config.yaml")
results = run_pipeline("BV1ABcsztEcY", mode="bv", provider="minimax", config=config)

# 批量处理UP主
results = run_pipeline("影视飓风", mode="user", max_videos=10)
```

### 故障排查

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| `bili 412 限流` | B站 API 频率限制 | 自动重试3次（含超时控制），等待后手动重试 |
| `音频下载失败` | 网络或权限问题 | 检查 `bili auth` 登录状态 |
| `关键帧0帧` | 场景变化阈值过高 | 自动回退等间隔采样，或降低 `scene_threshold` |
| `MINIMAX_API_KEY 未设置` | 环境变量缺失 | `export MINIMAX_API_KEY="..."` 或切换 `--provider omlx` |
| `oMLX 连接失败` | 本地服务未启动 | 启动 oMLX 或使用 `--provider minimax` |
| `yt-dlp cookies 错误` | 浏览器 cookies 过期 | 使用 `--cookies-from-browser chrome` 或重新登录 |
| `配置文件缺少必填字段` | config.yaml 不完整 | 补全 obsidian/omlx/provider 字段 |
| `路径跳出了 vault 根目录` | notes_dir/images_dir 配置有误 | 检查配置中是否包含 `../` 等跳转路径 |

## 运行测试

```bash
uv run pytest tests/ -v
```

## 技术栈

- **Python 3.12** + **uv** 包管理 + **hatchling** 构建
- **bilibili-cli** — B站数据获取
- **yt-dlp** — 视频下载
- **ffmpeg** — 视频处理和关键帧抽取
- **mlx-whisper** — Apple Silicon 本地语音转录（延迟加载，可选依赖）
- **oMLX** — 本地 LLM/VLM 推理（OpenAI 兼容 API）
- **MiniMax** — 云端 LLM 推理（Anthropic 兼容 API）
- **OpenAI SDK** — oMLX 客户端
- **Anthropic SDK** — MiniMax 客户端
- **Obsidian** — 知识管理和笔记展示

## License

MIT
