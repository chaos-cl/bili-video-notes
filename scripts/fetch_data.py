"""bili CLI 数据获取：视频信息、字幕、评论、音频"""

import logging
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

from scripts.common import get_work_dir

logger = logging.getLogger(__name__)

BV_RE = re.compile(r"BV[\w]{10}")


_BILI_CALL_INTERVAL = 2  # 每次 bili 调用间隔秒数，防限流


_RATE_LIMIT_RE = re.compile(r"412|precondition|rate.?limit", re.IGNORECASE)


def _run_bili(args: list[str], retries: int = 3, timeout: int = 120) -> str:
    """运行 bili 命令，返回 stdout。412 限流时自动重试"""
    time.sleep(_BILI_CALL_INTERVAL)
    for attempt in range(retries):
        result = subprocess.run(
            ["bili", *args], capture_output=True, text=True, timeout=timeout,
        )
        # 只检查 stderr 和 stdout 中的 ok 字段，避免字幕时间戳里的数字误判
        is_rate_limited = (
            _RATE_LIMIT_RE.search(result.stderr)
            or (result.returncode != 0 and _RATE_LIMIT_RE.search(result.stdout))
        )
        if result.returncode == 0 and not is_rate_limited:
            return result.stdout
        if is_rate_limited:
            wait = 5 * (attempt + 1)
            logger.warning("bili 412 限流，等待 %ds 后重试 (%d/%d)", wait, attempt + 1, retries)
            time.sleep(wait)
            continue
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, ["bili", *args], result.stdout, result.stderr)
    raise RuntimeError(f"bili 命令重试 {retries} 次后仍失败: {' '.join(args)}")


def _run_bili_yaml(args: list[str]) -> dict:
    """运行 bili 带 --yaml，返回解析后的 dict"""
    stdout = _run_bili([*args, "--yaml"])
    return yaml.safe_load(stdout)


def resolve_user(user_input: str) -> str:
    """解析用户输入为 UID：纯数字直返，否则搜索"""
    if user_input.isdigit():
        return user_input
    data = _run_bili_yaml(["search", user_input, "--type", "user", "--max", "1"])
    results = data.get("data", [])
    if isinstance(results, dict):
        results = results.get("results", [])
    if not results:
        raise ValueError(f"未找到用户: {user_input}")
    return str(results[0].get("id", results[0].get("uid", "")))


def resolve_input(raw_input: str, mode: str = "auto", max_videos: int = 5) -> list[str]:
    """统一解析输入为 BV 号列表

    mode: "bv", "url", "user", 或 "auto"（自动猜测）
    """
    if mode == "bv":
        bv_match = BV_RE.search(raw_input)
        if bv_match:
            return [bv_match.group()]
        raise ValueError(f"输入不是有效的 BV 号: {raw_input}")

    if mode == "url":
        return _resolve_url(raw_input)

    if mode == "user":
        uid = resolve_user(raw_input)
        return _fetch_user_videos(uid, raw_input, max_videos)

    # mode == "auto": 自动猜测
    bv_match = BV_RE.search(raw_input)
    if bv_match:
        return [bv_match.group()]

    if "b23.tv" in raw_input:
        return _resolve_url(raw_input)

    if "bilibili.com" in raw_input:
        return _resolve_url(raw_input)

    # 当作 UP 主处理
    uid = resolve_user(raw_input)
    return _fetch_user_videos(uid, raw_input, max_videos)


def _resolve_url(raw_input: str) -> list[str]:
    """解析 URL/短链为 BV 号列表"""
    # b23.tv 短链重定向
    if "b23.tv" in raw_input:
        url = raw_input if raw_input.startswith("http") else f"https://{raw_input.strip()}"
        parsed = urlparse(url)
        if parsed.hostname not in ("b23.tv", "www.b23.tv"):
            raise ValueError(f"不支持的短链域名: {parsed.hostname}")
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=15) as resp:
            final_url = resp.url
        bv_match = BV_RE.search(final_url)
        if bv_match:
            return [bv_match.group()]
        raise ValueError(f"短链无法解析为 BV 号: {raw_input}")

    # bilibili.com URL 提取 BV 号
    if "bilibili.com" in raw_input:
        bv_match = BV_RE.search(raw_input)
        if bv_match:
            return [bv_match.group()]
        raise ValueError(f"URL 中未找到 BV 号: {raw_input}")

    raise ValueError(f"无法识别的 URL: {raw_input}")


def _fetch_user_videos(uid: str, raw_input: str, max_videos: int) -> list[str]:
    """获取 UP 主视频列表，失败时用搜索备选"""
    try:
        data = _run_bili_yaml(["user-videos", uid, "--max", str(max_videos)])
        raw = data.get("data", {})
        videos = raw.get("videos", raw) if isinstance(raw, dict) else raw
        if isinstance(videos, list) and videos:
            return [v["bvid"] for v in videos if v.get("bvid")]
    except (subprocess.CalledProcessError, RuntimeError) as e:
        logger.warning("user-videos 失败: %s，尝试 search 备选", e)

    # 备选：用 search --type video 搜索，按作者 UID 过滤
    try:
        data = _run_bili_yaml(["search", raw_input, "--type", "video", "--max", str(max_videos)])
        results = data.get("data", [])
        if isinstance(results, dict):
            results = results.get("results", [])
        if results:
            bvids = []
            for item in results:
                bv = item.get("bvid", "")
                author_uid = item.get("author", {}).get("id", 0)
                if bv and (str(author_uid) == str(uid) or not author_uid):
                    bvids.append(bv)
            if bvids:
                return bvids
    except Exception as e:
        logger.warning("search 备选也失败: %s", e)

    raise ValueError(f"无法获取 UP主 {raw_input} (UID:{uid}) 的视频列表")


def fetch_video_info(bvid: str) -> dict:
    """获取视频详情，返回扁平化 dict"""
    data = _run_bili_yaml(["video", bvid])
    v = data.get("data", {}).get("video", {})
    return {
        "bvid": v.get("bvid", bvid),
        "title": v.get("title", ""),
        "author": v.get("owner", {}).get("name", ""),
        "author_uid": v.get("owner", {}).get("id", 0),
        "duration": v.get("duration", ""),
        "duration_seconds": v.get("duration_seconds", 0),
        "url": v.get("url", f"https://www.bilibili.com/video/{bvid}"),
        "description": v.get("description", ""),
        "stats": v.get("stats", {}),
        "aid": v.get("aid", 0),
    }


def fetch_subtitle(bvid: str) -> dict:
    """获取字幕"""
    data = _run_bili_yaml(["video", bvid, "--subtitle"])
    sub = data.get("data", {}).get("subtitle", {})
    return {"available": sub.get("available", False), "text": sub.get("text", "")}


def fetch_comments(bvid: str) -> list[dict]:
    """获取评论列表"""
    data = _run_bili_yaml(["video", bvid, "--comments"])
    comments = data.get("data", {}).get("comments", [])
    return [
        {"author": c.get("author", {}).get("name", ""), "message": c.get("message", ""), "like": c.get("like", 0)}
        for c in comments
    ]


def download_audio(bvid: str, output_dir: Path) -> str | None:
    """下载音频，返回文件路径或 None"""
    output_dir.mkdir(parents=True, exist_ok=True)
    _run_bili(["audio", bvid, "--no-split", "-o", str(output_dir)])
    m4a_files = list(output_dir.glob("*.m4a"))
    return str(m4a_files[0]) if m4a_files else None


def fetch_all(bvid: str, work_dir: Path | None = None, need_audio: bool = False) -> dict:
    """获取单个视频的全部数据"""
    if work_dir is None:
        work_dir = get_work_dir(bvid)

    logger.info("获取视频信息: %s", bvid)
    video = fetch_video_info(bvid)

    logger.info("获取字幕: %s", bvid)
    subtitle = fetch_subtitle(bvid)

    logger.info("获取评论: %s", bvid)
    comments = fetch_comments(bvid)

    # 仅在无字幕且需要转录时才下载音频
    audio_path = None
    if need_audio or not subtitle.get("available"):
        logger.info("下载音频: %s", bvid)
        try:
            audio_path = download_audio(bvid, work_dir)
        except Exception as e:
            logger.warning("音频下载失败 %s: %s", bvid, e)

    return {
        "video": video,
        "subtitle": subtitle,
        "comments": comments,
        "audio_path": audio_path,
    }
