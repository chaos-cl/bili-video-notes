"""transcribe_audio 测试"""

from pathlib import Path
from unittest.mock import patch

from scripts.transcribe_audio import _format_timestamp, format_srt, transcribe


class TestFormatTimestamp:
    def test_basic(self):
        assert _format_timestamp(0.0) == "00:00:00,000"

    def test_with_milliseconds(self):
        assert _format_timestamp(65.123) == "00:01:05,123"

    def test_hours(self):
        assert _format_timestamp(3661.5) == "01:01:01,500"

    def test_rounding(self):
        assert _format_timestamp(1.9999) == "00:00:02,000"


class TestFormatSrt:
    def test_single_segment(self):
        segments = [{"start": 0.0, "end": 5.5, "text": " hello "}]
        srt = format_srt(segments)
        assert "1\n00:00:00,000 --> 00:00:05,500\nhello" in srt

    def test_multiple_segments(self):
        segments = [
            {"start": 0.0, "end": 2.0, "text": "first"},
            {"start": 2.5, "end": 5.0, "text": "second"},
        ]
        srt = format_srt(segments)
        assert "1\n00:00:00,000 --> 00:00:02,000\nfirst" in srt
        assert "2\n00:00:02,500 --> 00:00:05,000\nsecond" in srt
        assert srt.count("\n\n") == 1  # 两个 segment 之间一个空行分隔


class TestTranscribe:
    @patch("scripts.transcribe_audio.mlx_whisper")
    def test_basic(self, mock_mlx):
        mock_mlx.transcribe.return_value = {
            "text": "hello world",
            "segments": [{"start": 0.0, "end": 2.0, "text": "hello world"}],
        }
        config = {"whisper": {"model": "large-v3-turbo", "language": "zh", "device": "mlx"}}
        with patch("scripts.transcribe_audio._MODELSCOPE_CACHE") as mock_cache:
            mock_cache.__truediv__ = lambda s, k: Path("/nonexistent")
            result = transcribe(Path("/fake/audio.mp3"), config)

        assert result["text"] == "hello world"
        assert len(result["segments"]) == 1
        assert "1\n" in result["srt"]


class TestTranscribeLanguageAuto:
    @patch("scripts.transcribe_audio.mlx_whisper")
    def test_language_auto_not_passed(self, mock_mlx):
        mock_mlx.transcribe.return_value = {"text": "", "segments": []}
        config = {"whisper": {"model": "large-v3-turbo", "language": "auto", "device": "mlx"}}
        with patch("scripts.transcribe_audio._MODELSCOPE_CACHE") as mock_cache:
            mock_cache.__truediv__ = lambda s, k: Path("/nonexistent")
            transcribe(Path("/fake/audio.mp3"), config)

        call_kwargs = mock_mlx.transcribe.call_args
        assert "language" not in call_kwargs.kwargs
