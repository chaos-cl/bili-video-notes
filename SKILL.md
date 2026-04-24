---
name: bilibili-notes
description: "将 Bilibili 视频自动转换为结构化 Obsidian Markdown 笔记。支持单视频和UP主批量处理。当用户提到 bilibili 笔记、视频笔记、视频转笔记、B站笔记、Bilibili notes、处理视频时触发。"
triggers:
  - "bilibili 笔记"
  - "视频笔记"
  - "视频转笔记"
  - "B站笔记"
  - "bilibili notes"
  - "处理视频"
  - "生成笔记"
---

# Bilibili Notes Skill

将 Bilibili 视频自动转换为结构化 Obsidian Markdown 笔记。

## 快速使用

```bash
# 单个视频（BV号）
uv run python scripts/pipeline.py --bv BV1ABcsztEcY

# 单个视频（URL / 短链）
uv run python scripts/pipeline.py --url "https://www.bilibili.com/video/BV1ABcsztEcY"
uv run python scripts/pipeline.py --url "https://b23.tv/xxxxx"

# 批量处理 UP 主视频
uv run python scripts/pipeline.py --user "影视飓风"
uv run python scripts/pipeline.py --user 946974 --max 20

# 选择 LLM 提供者
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --provider minimax

# 强制重新生成（覆盖已有笔记并清理旧帧）
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --force

# 覆盖 vault 路径
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --vault /path/to/vault

# 使用自定义配置文件
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --config /path/to/config.yaml
```

## 流水线步骤

1. **resolve_input** — 按 mode 严格解析输入为 BV 号列表（BV号、URL、短链、UP主名/UID）
2. **fetch_all** — 调用 bili CLI 获取视频信息、字幕、评论；仅无字幕时下载音频
3. **transcribe** — 无字幕时用 mlx-whisper 本地转录音频（延迟加载，不阻塞其他流程）
4. **extract_keyframes** — 清理旧帧后用 ffmpeg 场景变化检测抽取关键帧，失败回退等间隔采样
5. **analyze_frames** — VLM 逐帧视觉识别生成文字描述（仅支持 OpenAI 兼容接口如 omlx；minimax 不支持图片输入，自动跳过）
6. **generate_note** — LLM 融合所有信息生成结构化 Markdown 笔记（YAML frontmatter 安全生成）

## 配置

编辑 `config.yaml`：
- `provider`: `omlx`（本地）或 `minimax`（云端）
- `omlx`: 本地模型服务地址和模型名，密钥从环境变量 `OMLX_API_KEY` 读取
- `minimax`: 云端 API 配置，密钥从环境变量 `MINIMAX_API_KEY` 读取
- `obsidian`: vault 路径和输出目录（路径会校验不跳出 vault 根目录）
- `frames`: 抽帧参数（阈值、最大帧数、最大宽度）
- `whisper`: 语音转录模型配置

## 前置条件

| 依赖 | 用途 | 安装验证 |
|------|------|----------|
| Python 3.12 + uv | 运行环境 | `uv --version` |
| bili (bilibili-cli) | B站数据获取 | `bili --version` |
| ffmpeg | 视频处理/抽帧 | `ffmpeg -version` |
| yt-dlp | 视频下载 | `yt-dlp --version` |
| oMLX 服务 | 本地 LLM/VLM 推理（可选） | `curl localhost:8000/v1/models` |
| mlx-whisper | 本地语音转录（可选） | `uv sync --extra whisper` |

## 输出

- 笔记: `{vault_path}/{notes_dir}/标题(BV号).md`
- 图片: `{vault_path}/{images_dir}/BV号/frame_NNN.png`
- 转录: `work/BV号/transcript.txt`

## 故障处理

- **bili 412 限流**: 自动重试3次（5s/10s/15s递增等待），每次调用间隔2秒
- **字幕不可用**: 仅在无字幕时自动下载音频并用 whisper 转录，减少不必要的网络和磁盘开销
- **关键帧0帧**: 场景检测失败后自动回退到等间隔采样模式
- **oMLX 未启动**: 帧分析和笔记生成会失败，可切换 `--provider minimax` 使用云端
- **VLM 帧分析**: 仅 omlx (OpenAI 兼容) 支持图片输入；minimax 不支持视觉能力，自动跳过帧分析不影响笔记生成
- **fetch_all 失败**: 视为硬失败，不会生成失真的占位笔记
- **--force 模式**: 同步清理旧笔记、旧帧文件和临时产物，确保重跑结果干净
