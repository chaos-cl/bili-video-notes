"""analyze_frames 测试"""

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.analyze_frames import _encode_image, analyze_frames


class TestEncodeImage:
    """base64 编码测试"""

    def test_encodes_png_to_base64(self, tmp_path):
        png = tmp_path / "test.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        result = _encode_image(png)
        assert result == base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.png"
        f.write_bytes(b"")
        assert _encode_image(f) == ""


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    return resp


def _sample_frames(tmp_path) -> list[dict]:
    frames = []
    for i in range(5):
        p = tmp_path / f"frame_{i:03d}.png"
        p.write_bytes(b"\x89PNG_fake")
        frames.append(
            {"index": i, "path": str(p), "filename": f"frame_{i:03d}.png"}
        )
    return frames


class TestAnalyzeFrames:
    """单帧与分批分析测试 — 固定使用本地 VLM"""

    @patch("scripts.analyze_frames.get_vlm_client")
    def test_single_frame(self, mock_get_vlm, config, tmp_path):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            "一个在演讲的人"
        )
        mock_get_vlm.return_value = (mock_client, "test-vlm-model")

        frames = _sample_frames(tmp_path)[:1]
        results = analyze_frames(frames, config)

        assert len(results) == 1
        assert results[0]["description"] == "一个在演讲的人"
        assert results[0]["index"] == 0
        mock_client.chat.completions.create.assert_called_once()

    @patch("scripts.analyze_frames.get_vlm_client")
    def test_multiple_frames(self, mock_get_vlm, config, tmp_path):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _mock_response(f"描述{i}") for i in range(5)
        ]
        mock_get_vlm.return_value = (mock_client, "test-vlm-model")

        frames = _sample_frames(tmp_path)
        results = analyze_frames(frames, config)

        assert len(results) == 5
        for i, r in enumerate(results):
            assert r["description"] == f"描述{i}"
        assert mock_client.chat.completions.create.call_count == 5

    @patch("scripts.analyze_frames.get_vlm_client")
    def test_result_preserves_original_fields(
        self, mock_get_vlm, config, tmp_path
    ):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response("ok")
        mock_get_vlm.return_value = (mock_client, "test-vlm-model")

        frames = _sample_frames(tmp_path)[:1]
        results = analyze_frames(frames, config)

        assert results[0]["path"] == frames[0]["path"]
        assert results[0]["filename"] == frames[0]["filename"]

    @patch("scripts.analyze_frames.get_vlm_client")
    def test_uses_vlm_model_not_llm_model(self, mock_get_vlm, config, tmp_path):
        """验证使用的是 vlm_model 而非 llm_model"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response("ok")
        mock_get_vlm.return_value = (mock_client, "Qwen3-VL-8B-Instruct-MLX-4bit")

        frames = _sample_frames(tmp_path)[:1]
        analyze_frames(frames, config)

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("model") == "Qwen3-VL-8B-Instruct-MLX-4bit"

    @patch("scripts.analyze_frames.get_vlm_client")
    def test_ignores_provider_setting(self, mock_get_vlm, config, tmp_path):
        """验证即使 provider=minimax，帧分析仍使用本地 VLM"""
        config["provider"] = "minimax"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response("本地分析")
        mock_get_vlm.return_value = (mock_client, "test-vlm-model")

        frames = _sample_frames(tmp_path)[:1]
        results = analyze_frames(frames, config)

        assert results[0]["description"] == "本地分析"
        mock_get_vlm.assert_called_once_with(config)


class TestAnalyzeFramesFailure:
    """API 异常跳过逻辑测试"""

    @patch("scripts.analyze_frames.get_vlm_client")
    def test_api_failure_skips_frame(self, mock_get_vlm, config, tmp_path):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ConnectionError(
            "timeout"
        )
        mock_get_vlm.return_value = (mock_client, "test-vlm-model")

        frames = _sample_frames(tmp_path)[:2]
        results = analyze_frames(frames, config)

        assert len(results) == 2
        assert all(r["description"] == "" for r in results)

    @patch("scripts.analyze_frames.get_vlm_client")
    def test_partial_failure(self, mock_get_vlm, config, tmp_path):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _mock_response("正常描述"),
            RuntimeError("API error"),
            _mock_response("恢复描述"),
        ]
        mock_get_vlm.return_value = (mock_client, "test-vlm-model")

        frames = _sample_frames(tmp_path)[:3]
        results = analyze_frames(frames, config)

        assert results[0]["description"] == "正常描述"
        assert results[1]["description"] == ""
        assert results[2]["description"] == "恢复描述"
