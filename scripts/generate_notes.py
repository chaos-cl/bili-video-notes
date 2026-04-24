"""oMLX LLM 融合信息生成 Markdown 笔记"""

import logging
import re
from datetime import date
from pathlib import Path

import yaml

from scripts.common import get_omlx_client, get_llm_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
你是一个视频笔记生成助手。根据提供的视频信息和内容，生成结构化的笔记。

严格按以下 YAML 格式输出（用 --- 分隔）：

---
summary: |
  2-3句话的视频概要
detailed_notes: |
  详细的笔记内容，用 Markdown 格式
comments_section: |
  精选评论摘要
tags: "#bilibili #标签1 #标签2"
---

注意：
- summary: 2-3句简洁概要
- detailed_notes: 用 Markdown 列表、标题组织，保留关键信息
- comments_section: 挑选有代表性的评论
- tags: 用空格分隔的标签字符串
"""

_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


_MAX_CONTENT_CHARS = 80000


def _build_prompt(
    video_info: dict,
    subtitle_text: str,
    transcript_text: str,
    frames: list[dict],
    comments: list[dict],
) -> str:
    """构建 LLM prompt，带长度截断防止超上下文"""
    parts = []

    parts.append("## 视频信息")
    parts.append(f"标题: {video_info.get('title', '')}")
    parts.append(f"UP主: {video_info.get('author', '')}")
    parts.append(f"时长: {video_info.get('duration', '')}")
    parts.append(f"简介: {video_info.get('description', '')}")

    if subtitle_text:
        parts.append(f"\n## 字幕内容\n{subtitle_text[:_MAX_CONTENT_CHARS]}")

    if transcript_text:
        text = transcript_text[:_MAX_CONTENT_CHARS] if not subtitle_text else transcript_text[:_MAX_CONTENT_CHARS // 2]
        parts.append(f"\n## 语音转录\n{text}")

    if frames:
        parts.append("\n## 关键帧描述")
        for f in frames:
            desc = f.get("description", "")
            idx = f.get("index", "")
            parts.append(f"- 帧{idx}: {desc}")

    if comments:
        parts.append("\n## 精选评论")
        for c in comments[:20]:
            parts.append(f"- {c.get('author', '匿名')}: {c.get('message', '')} (赞:{c.get('like', 0)})")

    return "\n".join(parts)


def _parse_llm_output(raw: str) -> dict:
    """解析 LLM YAML 输出为 sections dict"""
    try:
        match = re.search(r"---\s*\n(.*?)\n---", raw, re.DOTALL)
        if match:
            parsed = yaml.safe_load(match.group(1))
            if isinstance(parsed, dict):
                return parsed
    except yaml.YAMLError:
        logger.warning("YAML 解析失败，尝试整段解析")
    try:
        parsed = yaml.safe_load(raw)
        if isinstance(parsed, dict):
            return parsed
    except yaml.YAMLError:
        pass
    return {
        "summary": raw[:200],
        "detailed_notes": raw,
        "comments_section": "",
        "tags": "#bilibili",
    }


def _sanitize_filename(title: str, bvid: str) -> str:
    """生成安全文件名"""
    safe_title = _ILLEGAL_CHARS.sub("_", title)[:80].strip("_ ")
    return f"{safe_title}({bvid}).md"


def _format_note(
    video_info: dict,
    summary: str,
    detailed_notes: str,
    comments_section: str,
    tags: str,
    frames: list[dict],
) -> str:
    """生成最终 Markdown"""
    bvid = video_info.get("bvid", "")
    title = video_info.get("title", "")
    author = video_info.get("author", "")
    duration = video_info.get("duration", "")
    url = video_info.get("url", "")

    frontmatter = {
        "title": title,
        "bvid": bvid,
        "author": author,
        "duration": duration,
        "url": url,
        "date": date.today().isoformat(),
        "tags": ["bilibili"],
    }

    lines = [
        "---",
        yaml.safe_dump(frontmatter, allow_unicode=True, default_flow_style=False).strip(),
        "---",
        "",
        f"# {title}",
        f"> 来源: [{bvid}]({url}) | UP主: {author} | 时长: {duration}",
        "",
        "## 概要",
        summary.strip() if summary else "",
        "",
    ]

    if frames:
        images_dir = video_info.get("_images_dir", "video-notes-images")
        lines.append("## 关键帧")
        for f in frames:
            fname = f.get("filename", f"frame_{f.get('index', 0):03d}.png")
            lines.append(f"![{fname}](../{images_dir}/{bvid}/{fname})")
            desc = f.get("description", "")
            if desc:
                lines.append(f"> {desc}")
            lines.append("")
        lines.append("")

    lines.extend([
        "## 详细笔记",
        detailed_notes.strip() if detailed_notes else "",
        "",
        "## 精选评论",
        comments_section.strip() if comments_section else "",
        "",
        "## 标签",
        tags.strip() if tags else "#bilibili",
        "",
    ])

    return "\n".join(lines)


def _call_llm(prompt: str, config: dict, provider: str | None = None) -> str:
    """调用 LLM，根据 provider 选择 OpenAI 或 Anthropic 格式"""
    client, model, api_type = get_llm_client(config, provider)

    if api_type == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        # 过滤 ThinkingBlock，只取 TextBlock
        return "\n".join(block.text for block in response.content if hasattr(block, "text"))
    else:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content


def generate_note(
    video_info: dict,
    subtitle_text: str,
    transcript_text: str,
    frames: list[dict],
    comments: list[dict],
    notes_dir: Path,
    config: dict,
    provider: str | None = None,
) -> Path:
    """完整生成流程：构建 prompt -> 调用 LLM -> 解析 -> 写文件"""
    prompt = _build_prompt(video_info, subtitle_text, transcript_text, frames, comments)

    raw = _call_llm(prompt, config, provider)
    sections = _parse_llm_output(raw)

    notes_dir.mkdir(parents=True, exist_ok=True)
    filename = _sanitize_filename(video_info.get("title", ""), video_info.get("bvid", ""))

    note_content = _format_note(
        video_info=video_info,
        summary=sections.get("summary", ""),
        detailed_notes=sections.get("detailed_notes", ""),
        comments_section=sections.get("comments_section", ""),
        tags=sections.get("tags", ""),
        frames=frames,
    )

    note_path = notes_dir / filename
    note_path.write_text(note_content, encoding="utf-8")
    logger.info("笔记已生成: %s", note_path)
    return note_path
