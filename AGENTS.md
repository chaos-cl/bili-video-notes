# Bilibili Notes — AI Agent 入口

## 这是什么

一个将 Bilibili 视频自动转换为结构化 Obsidian Markdown 笔记的命令行工具。

## 我能做什么

- 给我一个视频链接或BV号，我帮你生成一份包含概要、关键帧、详细笔记和评论的 Markdown 笔记
- 给我一个UP主名称，我帮你批量生成他/她的视频笔记
- 笔记自动保存到 Obsidian vault

## 怎么用

```bash
# 单个视频
uv run python scripts/pipeline.py --bv BV1ABcsztEcY

# 视频URL
uv run python scripts/pipeline.py --url "https://www.bilibili.com/video/BV1ABcsztEcY"

# b23.tv 短链
uv run python scripts/pipeline.py --url "https://b23.tv/xxxxx"

# 批量处理UP主视频
uv run python scripts/pipeline.py --user "影视飓风"
uv run python scripts/pipeline.py --user 946974 --max 50

# 选择 AI 提供者（默认 omlx 本地）
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --provider minimax

# 强制重新生成
uv run python scripts/pipeline.py --bv BV1ABcsztEcY --force
```

## 首次使用前：环境配置

按顺序执行以下步骤配置环境：

```bash
# 1. 安装依赖
uv sync

# 2. 验证外部工具
bili status       # bilibili-cli，需要登录认证
ffmpeg -version   # 视频处理
yt-dlp --version  # 视频下载

# 3. 检查 AI 服务（二选一）
curl localhost:8000/v1/models     # oMLX 本地推理
echo $MINIMAX_API_KEY             # MiniMax 云端推理

# 4. 修改配置
# 编辑 config.yaml，设置 obsidian.vault_path 为你的 Obsidian 仓库路径
```

### 外部工具安装（如未安装）

```bash
# bilibili-cli — 参考 https://github.com/public-clis/bilibili-cli
brew install bilibili-cli
bili auth login

# ffmpeg
brew install ffmpeg

# yt-dlp
brew install yt-dlp
```

### 配置文件说明

编辑 `config.yaml`：

```yaml
provider: "omlx"                    # omlx（本地）或 minimax（云端）

omlx:
  base_url: "http://localhost:8000/v1"
  llm_model: "Qwen3.6-35B-A3B-nvfp4"
  vlm_model: "Qwen3-VL-8B-Instruct-MLX-4bit"

minimax:
  base_url: "https://api.minimaxi.com/anthropic"
  api_key_env: "MINIMAX_API_KEY"
  model: "MiniMax-M2.7"

obsidian:
  vault_path: "~/Documents/Bilibili/Bilibili"  # 改成你的 vault 路径
  notes_dir: "video-notes"
  images_dir: "video-notes-images"
```

## 流水线做了什么

1. 解析输入 → BV 号列表
2. 获取视频信息、字幕、评论、音频
3. 无字幕时用 mlx-whisper 转录音频
4. ffmpeg 抽取关键帧图片
5. VLM 分析每帧画面生成描述
6. LLM 融合所有信息生成 Markdown 笔记
7. 保存到 Obsidian vault

## 输出

- 笔记: `{vault}/video-notes/标题(BV号).md`
- 图片: `{vault}/video-notes-images/BV号/frame_NNN.png`

## 故障排查

| 问题 | 解决 |
|------|------|
| bili 未认证 | `bili auth login` |
| MINIMAX_API_KEY 未设置 | `export MINIMAX_API_KEY="..."` 或用 `--provider omlx` |
| oMLX 连接失败 | 启动本地 oMLX 服务或用 `--provider minimax` |
| yt-dlp cookies 错误 | 检查浏览器登录状态 |

## 测试

```bash
uv run pytest tests/ -v
```
