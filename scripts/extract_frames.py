"""从 B 站视频抽取关键帧：yt-dlp 下载视频 + ffmpeg 场景变化检测"""

import logging
import re
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

BILI_URL = "https://www.bilibili.com/video/{bvid}"


def download_video(bvid: str, output_dir: Path, browser: str = "chrome") -> Path:
    """用 yt-dlp 下载视频到指定目录，返回文件路径"""
    page_url = BILI_URL.format(bvid=bvid)
    output_template = str(output_dir / "video.%(ext)s")
    result = subprocess.run(
        [
            "yt-dlp",
            "--cookies-from-browser", browser,
            "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "-o", output_template,
            "--merge-output-format", "mp4",
            page_url,
        ],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 下载失败: {result.stderr.strip()}")
    # 查找下载的文件
    for ext in ["mp4", "mkv", "webm", "flv"]:
        files = list(output_dir.glob(f"video.{ext}"))
        if files:
            return files[0]
    raise FileNotFoundError(f"视频文件未找到: {output_dir}")


def _get_duration(video_path: Path) -> float:
    """获取视频时长（秒）"""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def extract_keyframes(video_path: Path, output_dir: Path, config: dict) -> list[Path]:
    """用 ffmpeg 场景变化检测抽取关键帧，失败时回退到等间隔采样"""
    frames_cfg = config.get("frames", {})
    threshold = frames_cfg.get("scene_threshold", 0.3)
    max_frames = frames_cfg.get("max_frames", 20)
    max_width = frames_cfg.get("max_width", 1920)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 先尝试场景变化检测
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf",
        f"select='gt(scene,{threshold})',showinfo,scale='min({max_width},iw)':'-2'",
        "-fps_mode", "vfr",
        "-frames:v", str(max_frames),
        "-q:v", "2",
        str(output_dir / "scene_%03d.png"),
    ]

    logger.info("ffmpeg 场景检测: %s", " ".join(cmd))
    subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    frames = sorted(output_dir.glob("scene_*.png"))
    if frames:
        # 重命名为标准格式
        renamed = []
        for i, f in enumerate(frames[:max_frames], 1):
            new_name = output_dir / f"frame_{i:03d}.png"
            f.rename(new_name)
            renamed.append(new_name)
        # 清理多余的帧
        for f in frames[max_frames:]:
            f.unlink()
        logger.info("场景检测抽取到 %d 帧", len(renamed))
        return renamed

    # 回退：等间隔采样
    logger.info("场景检测无输出，使用等间隔采样")
    duration = _get_duration(video_path)
    if duration <= 0:
        logger.warning("无法获取视频时长")
        return []

    interval = max(duration / max_frames, 5)
    fps = 1.0 / interval

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"fps={fps:.4f},scale='min({max_width},iw)':'-2'",
        "-frames:v", str(max_frames),
        "-q:v", "2",
        str(output_dir / "frame_%03d.png"),
    ]

    logger.info("ffmpeg 等间隔采样: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    frames = sorted(output_dir.glob("frame_*.png"))
    if not frames and result.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败: {result.stderr.strip()}")

    logger.info("等间隔采样抽取到 %d 帧", len(frames))
    return frames


def get_frame_timestamps(frames: list[Path]) -> list[dict]:
    """从帧文件名解析信息: frame_001.png -> {index, filename, path}"""
    result = []
    for f in frames:
        m = re.match(r"frame_(\d+)", f.name)
        if not m:
            continue
        result.append({
            "index": int(m.group(1)),
            "filename": f.name,
            "path": str(f),
        })
    return result
