"""extract_frames 测试：mock 所有外部调用"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.extract_frames import (
    download_video,
    extract_keyframes,
    get_frame_timestamps,
)


class TestDownloadVideo:
    """yt-dlp 下载视频 mock 测试"""

    @patch("scripts.extract_frames.subprocess.run")
    def test_success(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )
        fake_video = tmp_path / "video.mp4"
        fake_video.write_bytes(b"fake video data")

        result = download_video("BV1test", tmp_path)
        assert result == fake_video
        assert isinstance(result, Path)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "yt-dlp" in args
        assert "--cookies-from-browser" in args
        assert "BV1test" in " ".join(args)

    @patch("scripts.extract_frames.subprocess.run")
    def test_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="error"
        )
        with pytest.raises(RuntimeError, match="yt-dlp 下载失败"):
            download_video("BV1bad", tmp_path)

    @patch("scripts.extract_frames.subprocess.run")
    def test_file_not_found(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr=""
        )
        with pytest.raises(FileNotFoundError, match="视频文件未找到"):
            download_video("BV1empty", tmp_path)


class TestExtractKeyframes:
    """ffmpeg 命令参数与输出验证"""

    @patch("scripts.extract_frames.subprocess.run")
    def test_scene_detection_success(self, mock_run, tmp_path, config):
        # 模拟 ffmpeg 场景检测输出了 scene_ 文件
        for i in range(1, 4):
            (tmp_path / f"scene_{i:03d}.png").write_bytes(b"fake")

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        frames = extract_keyframes("/tmp/test.mp4", tmp_path, config)
        assert len(frames) == 3
        # 场景检测帧被重命名为 frame_*.png
        assert all(f.name.startswith("frame_") for f in frames)
        # scene_ 文件应被重命名，不再存在
        assert len(list(tmp_path.glob("scene_*.png"))) == 0

    @patch("scripts.extract_frames.subprocess.run")
    def test_scene_detection_excess_frames_trimmed(self, mock_run, tmp_path, config):
        # 模拟超过 max_frames(20) 的场景帧
        for i in range(1, 30):
            (tmp_path / f"scene_{i:03d}.png").write_bytes(b"fake")

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        frames = extract_keyframes("/tmp/test.mp4", tmp_path, config)
        # 只保留 max_frames 个
        assert len(frames) == 20

    @patch("scripts.extract_frames._get_duration")
    @patch("scripts.extract_frames.subprocess.run")
    def test_fallback_periodic_sampling(self, mock_run, mock_dur, tmp_path, config):
        """场景检测无输出时回退到等间隔采样"""
        mock_dur.return_value = 120.0  # 2分钟视频
        # 第一次 ffmpeg 场景检测无输出（没有 scene_ 文件）
        # 第二次 ffmpeg 等间隔采样输出 frame_ 文件
        for i in range(1, 5):
            (tmp_path / f"frame_{i:03d}.png").write_bytes(b"fake")

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        frames = extract_keyframes("/tmp/test.mp4", tmp_path, config)
        assert len(frames) == 4
        # 验证调用了两次 ffmpeg（场景检测 + 等间隔）
        assert mock_run.call_count == 2

    @patch("scripts.extract_frames._get_duration")
    @patch("scripts.extract_frames.subprocess.run")
    def test_fallback_no_duration(self, mock_run, mock_dur, tmp_path, config):
        """等间隔采样时无法获取时长，返回空列表"""
        mock_dur.return_value = 0
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        frames = extract_keyframes("/tmp/test.mp4", tmp_path, config)
        assert frames == []

    @patch("scripts.extract_frames._get_duration")
    @patch("scripts.extract_frames.subprocess.run")
    def test_ffmpeg_nonzero_but_has_scene_output(self, mock_run, mock_dur, tmp_path, config):
        """ffmpeg 返回非零但有场景输出 → 正常返回"""
        (tmp_path / "scene_001.png").write_bytes(b"fake")
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="warn")

        frames = extract_keyframes("/tmp/test.mp4", tmp_path, config)
        assert len(frames) == 1

    @patch("scripts.extract_frames._get_duration")
    @patch("scripts.extract_frames.subprocess.run")
    def test_both_methods_fail(self, mock_run, mock_dur, tmp_path, config):
        """场景检测和等间隔采样都失败 → 抛异常"""
        mock_dur.return_value = 120.0
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        with pytest.raises(RuntimeError, match="ffmpeg 失败"):
            extract_keyframes("bad_url", tmp_path, config)

    @patch("scripts.extract_frames.subprocess.run")
    def test_local_file_path(self, mock_run, tmp_path, config):
        """本地文件路径作为 video_url"""
        (tmp_path / "scene_001.png").write_bytes(b"fake")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        extract_keyframes("/tmp/test.mp4", tmp_path, config)
        cmd = mock_run.call_args[0][0]
        assert "/tmp/test.mp4" in cmd


class TestGetFrameTimestamps:
    """帧信息解析"""

    def test_parse_frames(self):
        frames = [Path("/out/frame_001.png"), Path("/out/frame_007.png")]
        result = get_frame_timestamps(frames)
        assert len(result) == 2
        assert result[0] == {
            "index": 1,
            "filename": "frame_001.png",
            "path": "/out/frame_001.png",
        }
        assert result[1]["index"] == 7

    def test_empty_list(self):
        assert get_frame_timestamps([]) == []

    def test_non_matching_filename(self):
        frames = [Path("/out/thumbnail.png")]
        assert get_frame_timestamps(frames) == []

    def test_sequential_indices(self):
        frames = [Path(f"/out/frame_{i:03d}.png") for i in range(1, 6)]
        result = get_frame_timestamps(frames)
        indices = [r["index"] for r in result]
        assert indices == [1, 2, 3, 4, 5]
