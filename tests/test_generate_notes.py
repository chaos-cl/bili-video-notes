"""generate_notes 测试"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.generate_notes import (
    _build_prompt,
    _call_llm,
    _format_note,
    _parse_llm_output,
    _sanitize_filename,
    generate_note,
)


def _sample_video_info(**overrides):
    base = {
        "bvid": "BV1xx411c7mD",
        "title": "测试视频标题",
        "author": "测试UP主",
        "duration": "10:30",
        "url": "https://www.bilibili.com/video/BV1xx411c7mD",
        "description": "这是一个测试视频的简介",
        "aid": 12345,
        "stats": {"view": 1000, "like": 100},
    }
    base.update(overrides)
    return base


def _sample_comments(n=3):
    return [
        {"author": f"用户{i}", "message": f"评论内容{i}", "like": i * 10}
        for i in range(n)
    ]


def _sample_frames(n=2):
    return [
        {"index": i, "filename": f"frame_{i:03d}.png", "description": f"帧描述{i}"}
        for i in range(n)
    ]


def _mock_openai_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    return resp


def _mock_anthropic_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock()]
    resp.content[0].text = text
    return resp


class TestBuildPrompt:
    """prompt 构建测试"""

    def test_basic_video_info(self):
        prompt = _build_prompt(
            _sample_video_info(), "", "", [], []
        )
        assert "测试视频标题" in prompt
        assert "测试UP主" in prompt
        assert "这是一个测试视频的简介" in prompt

    def test_with_subtitle(self):
        prompt = _build_prompt(
            _sample_video_info(), "字幕文本内容", "", [], []
        )
        assert "字幕内容" in prompt
        assert "字幕文本内容" in prompt

    def test_with_transcript(self):
        prompt = _build_prompt(
            _sample_video_info(), "", "转录文本内容", [], []
        )
        assert "语音转录" in prompt
        assert "转录文本内容" in prompt

    def test_with_frames(self):
        frames = _sample_frames(3)
        prompt = _build_prompt(
            _sample_video_info(), "", "", frames, []
        )
        assert "关键帧描述" in prompt
        assert "帧描述0" in prompt

    def test_with_comments(self):
        comments = _sample_comments(5)
        prompt = _build_prompt(
            _sample_video_info(), "", "", [], comments
        )
        assert "精选评论" in prompt
        assert "用户0" in prompt

    def test_comments_capped_at_20(self):
        comments = _sample_comments(30)
        prompt = _build_prompt(
            _sample_video_info(), "", "", [], comments
        )
        assert "用户19" in prompt
        assert "用户29" not in prompt


class TestParseLlmOutput:
    """LLM 输出解析测试"""

    def test_valid_yaml(self):
        raw = """---
summary: |
  这是一个概要
detailed_notes: |
  详细笔记内容
comments_section: |
  评论摘要
tags: "#bilibili #测试"
---"""
        result = _parse_llm_output(raw)
        assert "概要" in result["summary"]
        assert "详细笔记" in result["detailed_notes"]
        assert "评论摘要" in result["comments_section"]
        assert "#测试" in result["tags"]

    def test_fallback_on_invalid_yaml(self):
        raw = "这不是YAML格式，只是一段普通文本"
        result = _parse_llm_output(raw)
        assert "summary" in result
        assert result["summary"] == raw[:200]
        assert result["tags"] == "#bilibili"


class TestSanitizeFilename:
    """文件名安全处理测试"""

    def test_normal_title(self):
        result = _sanitize_filename("正常标题", "BV1xx")
        assert result == "正常标题(BV1xx).md"

    def test_illegal_chars_replaced(self):
        result = _sanitize_filename('标题:包含/非法\\字符', "BV1xx")
        assert ":" not in result
        assert "/" not in result
        assert "\\" not in result
        assert result.endswith("(BV1xx).md")

    def test_long_title_truncated(self):
        long_title = "非常长的标题" * 30
        result = _sanitize_filename(long_title, "BV1xx")
        name_part = result[: result.index("(BV1xx)")]
        assert len(name_part) <= 80


class TestFormatNote:
    """Markdown 输出格式测试"""

    def test_frontmatter(self):
        note = _format_note(
            _sample_video_info(), "概要", "笔记", "评论",
            "#bilibili #测试", []
        )
        assert 'title: "测试视频标题"' in note
        assert 'bvid: "BV1xx411c7mD"' in note
        assert "date:" in note

    def test_header_structure(self):
        note = _format_note(
            _sample_video_info(), "概要", "笔记", "评论",
            "#bilibili #测试", []
        )
        assert "# 测试视频标题" in note
        assert "> 来源:" in note
        assert "## 概要" in note
        assert "## 详细笔记" in note
        assert "## 精选评论" in note
        assert "## 标签" in note

    def test_with_frames(self):
        frames = _sample_frames(2)
        note = _format_note(
            _sample_video_info(), "概要", "笔记", "评论",
            "#bilibili", frames
        )
        assert "## 关键帧" in note
        assert "![frame_000.png]" in note
        assert "> 帧描述0" in note

    def test_empty_sections_no_crash(self):
        note = _format_note(
            _sample_video_info(), "", "", "", "", []
        )
        assert "# 测试视频标题" in note


class TestCallLlm:
    """LLM 调用测试"""

    @patch("scripts.generate_notes.get_llm_client")
    def test_openai_provider(self, mock_get_client, config):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response("结果")
        mock_get_client.return_value = (mock_client, "test-model", "openai")

        result = _call_llm("测试 prompt", config, "omlx")
        assert result == "结果"
        mock_client.chat.completions.create.assert_called_once()

    @patch("scripts.generate_notes.get_llm_client")
    def test_anthropic_provider(self, mock_get_client, config):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response("MiniMax 结果")
        mock_get_client.return_value = (mock_client, "MiniMax-M2.7", "anthropic")

        result = _call_llm("测试 prompt", config, "minimax")
        assert result == "MiniMax 结果"
        mock_client.messages.create.assert_called_once()


class TestGenerateNote:
    """完整生成流程测试"""

    @patch("scripts.generate_notes.get_llm_client")
    def test_full_flow(self, mock_get_client, config, tmp_path):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            "---\nsummary: |\n  概要内容\ndetailed_notes: |\n  笔记内容\n"
            "comments_section: |\n  评论\n"
            'tags: "#bilibili #测试"\n---'
        )
        mock_get_client.return_value = (mock_client, "test-model", "openai")

        notes_dir = tmp_path / "notes"
        result = generate_note(
            video_info=_sample_video_info(),
            subtitle_text="字幕文本",
            transcript_text="",
            frames=_sample_frames(2),
            comments=_sample_comments(3),
            notes_dir=notes_dir,
            config=config,
        )

        assert result.exists()
        assert result.suffix == ".md"
        content = result.read_text(encoding="utf-8")
        assert "# 测试视频标题" in content
        assert "概要内容" in content

    @patch("scripts.generate_notes.get_llm_client")
    def test_creates_notes_dir(self, mock_get_client, config, tmp_path):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_openai_response(
            "---\nsummary: ok\ndetailed_notes: ok\ncomments_section: \n"
            "tags: #bilibili\n---"
        )
        mock_get_client.return_value = (mock_client, "test-model", "openai")

        notes_dir = tmp_path / "deep" / "nested" / "notes"
        result = generate_note(
            video_info=_sample_video_info(),
            subtitle_text="",
            transcript_text="",
            frames=[],
            comments=[],
            notes_dir=notes_dir,
            config=config,
        )

        assert result.exists()
        assert notes_dir.exists()

    @patch("scripts.generate_notes.get_llm_client")
    def test_minimax_provider(self, mock_get_client, config, tmp_path):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_anthropic_response(
            "---\nsummary: MiniMax 概要\ndetailed_notes: MiniMax 笔记\n"
            "comments_section: \ntags: #bilibili\n---"
        )
        mock_get_client.return_value = (mock_client, "MiniMax-M2.7", "anthropic")

        notes_dir = tmp_path / "notes"
        result = generate_note(
            video_info=_sample_video_info(),
            subtitle_text="",
            transcript_text="",
            frames=[],
            comments=[],
            notes_dir=notes_dir,
            config=config,
            provider="minimax",
        )

        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "MiniMax 概要" in content
        mock_client.messages.create.assert_called_once()
