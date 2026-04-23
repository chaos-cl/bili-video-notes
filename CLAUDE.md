# Bilibili Notes — Claude Code 项目上下文

## 项目概述

将 Bilibili 视频自动转换为结构化 Obsidian Markdown 笔记的 CLI 工具。

## 技能入口

当用户提到 bilibili 笔记、视频笔记、视频转笔记、B站笔记、处理视频时，调用 `SKILL.md` 中的流程。

## 快速调用

```bash
uv run python scripts/pipeline.py --bv <BV号>
uv run python scripts/pipeline.py --url <视频URL>
uv run python scripts/pipeline.py --user <UP主名或UID> --max <数量>
uv run python scripts/pipeline.py --bv <BV号> --provider minimax
```

## 环境自检

运行任务前先执行：

```bash
bili status && ffmpeg -version >/dev/null 2>&1 && yt-dlp --version >/dev/null 2>&1
```

若 `MINIMAX_API_KEY` 未设置，使用 `--provider omlx` 或提示用户设置。

## 关键文件

| 文件 | 职责 |
|------|------|
| `scripts/pipeline.py` | 流水线入口和 CLI |
| `scripts/fetch_data.py` | bili CLI 数据获取 |
| `scripts/extract_frames.py` | yt-dlp + ffmpeg 关键帧 |
| `scripts/transcribe_audio.py` | mlx-whisper 转录 |
| `scripts/analyze_frames.py` | VLM 帧分析 |
| `scripts/generate_notes.py` | LLM 笔记生成 |
| `scripts/common.py` | 配置、日志、API 客户端 |
| `config.yaml` | 运行时配置 |

## 测试

```bash
uv run pytest tests/ -v
```
