"""pipeline 测试"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.pipeline import process_single, run_pipeline


def _sample_video_info(**overrides):
    base = {
        "bvid": "BV1xx411c7mD",
        "title": "测试视频标题",
        "author": "测试UP主",
        "duration": "10:30",
        "url": "https://www.bilibili.com/video/BV1xx411c7mD",
        "description": "测试简介",
        "aid": 12345,
        "stats": {"view": 1000},
    }
    base.update(overrides)
    return base


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    return resp


@pytest.fixture
def mock_vault(tmp_path, config):
    """创建临时 vault 目录结构"""
    vault = tmp_path / "vault"
    notes_dir = vault / config["obsidian"]["notes_dir"]
    images_dir = vault / config["obsidian"]["images_dir"]
    notes_dir.mkdir(parents=True)
    images_dir.mkdir(parents=True)
    config["obsidian"]["vault_path"] = str(vault)
    return notes_dir, images_dir


class TestProcessSingle:
    """单个视频处理测试"""

    @patch("scripts.pipeline.generate_note")
    @patch("scripts.pipeline.analyze_frames")
    @patch("scripts.pipeline.download_video")
    @patch("scripts.pipeline.extract_keyframes")
    @patch("scripts.pipeline.transcribe")
    @patch("scripts.pipeline.fetch_all")
    @patch("scripts.pipeline.get_vault_paths")
    def test_with_subtitle(
        self, mock_vault_paths, mock_fetch, mock_transcribe,
        mock_extract_kf, mock_download, mock_analyze, mock_generate,
        config, tmp_path,
    ):
        notes_dir = tmp_path / "notes"
        images_dir = tmp_path / "images"
        notes_dir.mkdir()
        images_dir.mkdir()
        mock_vault_paths.return_value = (notes_dir, images_dir)

        mock_fetch.return_value = {
            "video": _sample_video_info(),
            "subtitle": {"available": True, "text": "字幕文本"},
            "comments": [{"author": "用户", "message": "评论", "like": 1}],
            "audio_path": "/tmp/audio.m4a",
        }
        mock_download.return_value = Path("/tmp/video.mp4")
        mock_extract_kf.return_value = [Path("/tmp/frame_001.png")]
        mock_analyze.return_value = [{"index": 1, "filename": "frame_001.png", "description": "帧描述"}]

        note_path = notes_dir / f"测试视频标题(BV1xx411c7mD).md"
        mock_generate.return_value = note_path

        result = process_single("BV1xx411c7mD", config, work_dir=tmp_path)

        # 有字幕，不应调用 transcribe
        mock_transcribe.assert_not_called()
        mock_generate.assert_called_once()
        assert result == note_path

    @patch("scripts.pipeline.generate_note")
    @patch("scripts.pipeline.analyze_frames")
    @patch("scripts.pipeline.download_video")
    @patch("scripts.pipeline.extract_keyframes")
    @patch("scripts.pipeline.transcribe")
    @patch("scripts.pipeline.fetch_all")
    @patch("scripts.pipeline.get_vault_paths")
    def test_with_provider(
        self, mock_vault_paths, mock_fetch, mock_transcribe,
        mock_extract_kf, mock_download, mock_analyze, mock_generate,
        config, tmp_path,
    ):
        notes_dir = tmp_path / "notes"
        images_dir = tmp_path / "images"
        notes_dir.mkdir()
        images_dir.mkdir()
        mock_vault_paths.return_value = (notes_dir, images_dir)

        mock_fetch.return_value = {
            "video": _sample_video_info(),
            "subtitle": {"available": True, "text": "字幕文本"},
            "comments": [],
            "audio_path": None,
        }
        mock_download.return_value = Path("/tmp/video.mp4")
        mock_extract_kf.return_value = []
        mock_generate.return_value = notes_dir / "out.md"

        process_single("BV1xx411c7mD", config, work_dir=tmp_path, provider="minimax")

        # 验证 provider 传递到 generate_note
        call_kwargs = mock_generate.call_args
        assert call_kwargs.kwargs.get("provider") == "minimax"

    @patch("scripts.pipeline.generate_note")
    @patch("scripts.pipeline.analyze_frames")
    @patch("scripts.pipeline.download_video")
    @patch("scripts.pipeline.extract_keyframes")
    @patch("scripts.pipeline.transcribe")
    @patch("scripts.pipeline.fetch_all")
    @patch("scripts.pipeline.get_vault_paths")
    def test_no_subtitle_triggers_transcribe(
        self, mock_vault_paths, mock_fetch, mock_transcribe,
        mock_extract_kf, mock_download, mock_analyze, mock_generate,
        config, tmp_path,
    ):
        notes_dir = tmp_path / "notes"
        images_dir = tmp_path / "images"
        notes_dir.mkdir()
        images_dir.mkdir()
        mock_vault_paths.return_value = (notes_dir, images_dir)

        mock_fetch.return_value = {
            "video": _sample_video_info(),
            "subtitle": {"available": False, "text": ""},
            "comments": [],
            "audio_path": "/tmp/audio.m4a",
        }
        mock_transcribe.return_value = {"text": "转录文本", "segments": [], "srt": ""}
        mock_download.return_value = Path("/tmp/video.mp4")
        mock_extract_kf.return_value = []
        mock_generate.return_value = notes_dir / "out.md"

        process_single("BV1xx411c7mD", config, work_dir=tmp_path)

        # 无字幕有音频，应调用 transcribe
        mock_transcribe.assert_called_once()

    @patch("scripts.pipeline.generate_note")
    @patch("scripts.pipeline.get_vault_paths")
    def test_skip_existing_note(
        self, mock_vault_paths, mock_generate, config, tmp_path,
    ):
        notes_dir = tmp_path / "notes"
        images_dir = tmp_path / "images"
        notes_dir.mkdir()
        images_dir.mkdir()
        mock_vault_paths.return_value = (notes_dir, images_dir)

        # 创建已有笔记
        existing = notes_dir / "已有笔记(BV1xx411c7mD).md"
        existing.write_text("已存在")

        result = process_single("BV1xx411c7mD", config, work_dir=tmp_path)

        mock_generate.assert_not_called()
        assert result == existing

    @patch("scripts.pipeline.generate_note")
    @patch("scripts.pipeline.fetch_all")
    @patch("scripts.pipeline.get_vault_paths")
    def test_fetch_failure_continues(
        self, mock_vault_paths, mock_fetch, mock_generate, config, tmp_path,
    ):
        notes_dir = tmp_path / "notes"
        images_dir = tmp_path / "images"
        notes_dir.mkdir()
        images_dir.mkdir()
        mock_vault_paths.return_value = (notes_dir, images_dir)

        mock_fetch.side_effect = RuntimeError("网络错误")
        mock_generate.return_value = notes_dir / "out.md"

        result = process_single("BV1xx411c7mD", config, work_dir=tmp_path)

        # fetch 失败但 generate_note 仍被调用（使用默认 video_info）
        mock_generate.assert_called_once()
        assert result == notes_dir / "out.md"


class TestRunPipeline:
    """批量处理测试"""

    @patch("scripts.pipeline.process_single")
    @patch("scripts.pipeline.resolve_input")
    @patch("scripts.pipeline.setup_logging")
    @patch("scripts.pipeline.load_config")
    def test_batch_processing(
        self, mock_load, mock_setup_log, mock_resolve, mock_process, config,
    ):
        mock_load.return_value = config
        mock_resolve.return_value = ["BV1xx0001", "BV1xx0002", "BV1xx0003"]

        path1 = Path("/tmp/notes/note1(BV1xx0001).md")
        path3 = Path("/tmp/notes/note3(BV1xx0003).md")
        mock_process.side_effect = [path1, None, path3]

        results = run_pipeline("测试UP主", mode="user", max_videos=3)

        assert len(results) == 2
        assert path1 in results
        assert path3 in results
        assert mock_process.call_count == 3

    @patch("scripts.pipeline.process_single")
    @patch("scripts.pipeline.resolve_input")
    @patch("scripts.pipeline.setup_logging")
    @patch("scripts.pipeline.load_config")
    def test_single_bv(
        self, mock_load, mock_setup_log, mock_resolve, mock_process, config,
    ):
        mock_load.return_value = config
        mock_resolve.return_value = ["BV1xx411c7mD"]

        note_path = Path("/tmp/notes/测试(BV1xx411c7mD).md")
        mock_process.return_value = note_path

        results = run_pipeline("BV1xx411c7mD")

        assert len(results) == 1
        assert results[0] == note_path
