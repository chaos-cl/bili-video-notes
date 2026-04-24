"""fetch_data.py 单元测试"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.fetch_data import (
    download_audio,
    fetch_all,
    fetch_comments,
    fetch_subtitle,
    fetch_video_info,
    resolve_input,
    resolve_user,
)


# ── helpers ──

def _yaml_response(data: dict) -> str:
    import yaml
    return yaml.dump({"data": data})


# ── TestResolveUser ──

class TestResolveUser:
    @patch("scripts.fetch_data._run_bili_yaml")
    def test_uid_direct(self, mock_yaml):
        assert resolve_user("123456") == "123456"
        mock_yaml.assert_not_called()

    @patch("scripts.fetch_data._run_bili_yaml")
    def test_name_search(self, mock_yaml):
        mock_yaml.return_value = {"data": {"results": [{"uid": 789, "name": "测试UP"}]}}
        assert resolve_user("测试UP") == "789"

    @patch("scripts.fetch_data._run_bili_yaml")
    def test_not_found(self, mock_yaml):
        mock_yaml.return_value = {"data": {"results": []}}
        with pytest.raises(ValueError, match="未找到用户"):
            resolve_user("不存在的用户")


# ── TestResolveInput ──

class TestResolveInput:
    def test_bv_direct(self):
        assert resolve_input("BV1xx411c7mD") == ["BV1xx411c7mD"]

    def test_url_extract(self):
        assert resolve_input("https://www.bilibili.com/video/BV1xx411c7mD?p=1") == ["BV1xx411c7mD"]

    @patch("scripts.fetch_data.urlopen")
    def test_short_link(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.url = "https://www.bilibili.com/video/BV1xx411c7mD"
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        assert resolve_input("https://b23.tv/abc123") == ["BV1xx411c7mD"]

    @patch("scripts.fetch_data._run_bili_yaml")
    def test_up_master_batch(self, mock_yaml):
        mock_yaml.side_effect = [
            {"data": {"results": [{"uid": 111, "name": "UP主"}]}},
            {"data": {"videos": [{"bvid": "BV1111111111", "title": "t1"}, {"bvid": "BV2222222222", "title": "t2"}]}},
        ]
        result = resolve_input("UP主", max_videos=2)
        assert result == ["BV1111111111", "BV2222222222"]


# ── TestFetchVideoInfo ──

class TestFetchVideoInfo:
    @patch("scripts.fetch_data._run_bili_yaml")
    def test_success(self, mock_yaml):
        mock_yaml.return_value = {
            "data": {
                "video": {
                    "bvid": "BV1xx411c7mD",
                    "title": "测试视频",
                    "owner": {"name": "UP主", "id": 123},
                    "duration": "10:30",
                    "duration_seconds": 630,
                    "url": "https://www.bilibili.com/video/BV1xx411c7mD",
                    "description": "简介",
                    "stats": {"view": 1000, "like": 50},
                    "aid": 456,
                }
            }
        }
        info = fetch_video_info("BV1xx411c7mD")
        assert info["title"] == "测试视频"
        assert info["author_uid"] == 123
        assert info["aid"] == 456


# ── TestFetchSubtitle ──

class TestFetchSubtitle:
    @patch("scripts.fetch_data._run_bili_yaml")
    def test_with_subtitle(self, mock_yaml):
        mock_yaml.return_value = {"data": {"subtitle": {"available": True, "text": "字幕内容"}}}
        result = fetch_subtitle("BV1xx411c7mD")
        assert result["available"] is True
        assert result["text"] == "字幕内容"

    @patch("scripts.fetch_data._run_bili_yaml")
    def test_no_subtitle(self, mock_yaml):
        mock_yaml.return_value = {"data": {"subtitle": {"available": False, "text": ""}}}
        result = fetch_subtitle("BV1xx411c7mD")
        assert result["available"] is False


# ── TestFetchComments ──

class TestFetchComments:
    @patch("scripts.fetch_data._run_bili_yaml")
    def test_success(self, mock_yaml):
        mock_yaml.return_value = {
            "data": {
                "comments": [
                    {"author": {"name": "用户A"}, "message": "好视频", "like": 10},
                    {"author": {"name": "用户B"}, "message": "不错", "like": 5},
                ]
            }
        }
        comments = fetch_comments("BV1xx411c7mD")
        assert len(comments) == 2
        assert comments[0]["author"] == "用户A"
        assert comments[1]["like"] == 5


# ── TestDownloadAudio ──

class TestDownloadAudio:
    @patch("scripts.fetch_data._run_bili")
    def test_download_params(self, mock_run):
        output_dir = Path("/tmp/test_audio")
        mock_run.return_value = ""
        # 不存在 m4a 文件
        with patch.object(Path, "glob", return_value=[]):
            result = download_audio("BV1xx411c7mD", output_dir)
        mock_run.assert_called_once_with(["audio", "BV1xx411c7mD", "--no-split", "-o", str(output_dir)])
        assert result is None

    @patch("scripts.fetch_data._run_bili")
    def test_download_found(self, mock_run):
        output_dir = Path("/tmp/test_audio")
        mock_run.return_value = ""
        fake_file = MagicMock()
        fake_file.__str__ = lambda s: "/tmp/test_audio/BV1xx.m4a"
        with patch.object(Path, "glob", return_value=[fake_file]):
            result = download_audio("BV1xx411c7mD", output_dir)
        assert result == "/tmp/test_audio/BV1xx.m4a"


# ── TestFetchAll ──

class TestFetchAll:
    @patch("scripts.fetch_data.download_audio", return_value="/tmp/test.m4a")
    @patch("scripts.fetch_data.fetch_comments", return_value=[{"author": "A", "message": "m", "like": 0}])
    @patch("scripts.fetch_data.fetch_subtitle", return_value={"available": False, "text": ""})
    @patch("scripts.fetch_data.fetch_video_info")
    def test_fetch_all(self, mock_info, mock_sub, mock_comments, mock_audio):
        mock_info.return_value = {
            "bvid": "BV1xx411c7mD", "title": "T", "author": "A",
            "author_uid": 1, "duration": "1:00", "duration_seconds": 60,
            "url": "https://example.com", "description": "", "stats": {}, "aid": 100,
        }
        result = fetch_all("BV1xx411c7mD", Path("/tmp/work"))
        assert result["video"]["bvid"] == "BV1xx411c7mD"
        assert result["audio_path"] == "/tmp/test.m4a"
        assert len(result["comments"]) == 1
