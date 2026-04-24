"""本地语音转录 — mlx-whisper"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ModelScope 缓存路径
_MODELSCOPE_CACHE = Path.home() / ".cache" / "modelscope" / "hub" / "models"


def _format_timestamp(seconds: float) -> str:
    """秒数转 SRT 时间格式 HH:MM:SS,mmm"""
    ms_total = int(round(seconds * 1000))
    h = ms_total // 3_600_000
    m = (ms_total % 3_600_000) // 60_000
    s = (ms_total % 60_000) // 1_000
    ms = ms_total % 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_srt(segments: list[dict]) -> str:
    """segments 列表转 SRT 字符串"""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _format_timestamp(seg["start"])
        end = _format_timestamp(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}")
    return "\n\n".join(lines)


def transcribe(audio_path: Path, config: dict) -> dict:
    """mlx-whisper 转录音频

    Returns:
        {"text": str, "segments": list, "srt": str}
    """
    try:
        import mlx_whisper
    except ImportError:
        raise ImportError(
            "mlx-whisper 未安装。语音转录需要 Apple Silicon Mac，请运行: "
            "uv add mlx-whisper modelscope"
        )

    wcfg = config["whisper"]
    model_name = wcfg["model"]

    # 优先使用 ModelScope 本地缓存，其次 HuggingFace
    local_path = _MODELSCOPE_CACHE / f"mlx-community/whisper-{model_name}"
    model_path = str(local_path) if local_path.exists() else f"mlx-community/whisper-{model_name}"

    kwargs: dict = {"path_or_hf_repo": model_path}
    if wcfg.get("language") and wcfg["language"] != "auto":
        kwargs["language"] = wcfg["language"]

    result = mlx_whisper.transcribe(str(audio_path), **kwargs)
    segments = result.get("segments", [])
    return {
        "text": result["text"],
        "segments": segments,
        "srt": format_srt(segments),
    }
